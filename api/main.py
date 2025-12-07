from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
from .database import get_db, engine, Base
from .models import User
from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_active_user,
    verify_password,
    get_password_hash
)
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create tables if not exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Financial Advisory (SFA)", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.security.audit_logger import AuditMiddleware
app.add_middleware(AuditMiddleware)

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

from pydantic import BaseModel
class ChatRequest(BaseModel):
    message: str

from backend.routing import run_ramas_pipeline

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: User = Depends(get_current_active_user)):
    # Simple in-memory history for context (last 2 interactions)
    # In production, use Redis or DB with SessionID
    global GLOBAL_HISTORY
    if 'GLOBAL_HISTORY' not in globals():
        GLOBAL_HISTORY = []
        
    # Append User Message
    full_context_query = request.message
    if GLOBAL_HISTORY:
        # Prepend last Q&A to provide context
        last_exchange = GLOBAL_HISTORY[-1]
        if len(GLOBAL_HISTORY) > 2:
            GLOBAL_HISTORY.pop(0) # Keep size small
            
        # We don't prepend to the actual string sent to the pipeline IF we modify pipeline to accept history.
        # But `run_ramas_pipeline` takes a string.
        # Quick Hack: Prepend context to the query if it looks like a follow-up ("it", "this", "that")
        low_msg = request.message.lower()
        if any(w in low_msg for w in ["this", "that", "it", "dates", "when"]):
            full_context_query = f"Context: {last_exchange['q']} -> {last_exchange['a']}\nUser Follow-up: {request.message}"
    
    response = run_ramas_pipeline(full_context_query)
    
    # Store History
    GLOBAL_HISTORY.append({"q": request.message, "a": response})
    
    return {"response": response}

from backend.analytics.metrics import get_key_metrics, get_revenue_trend, get_income_trend

@app.get("/api/dashboard/metrics")
async def dashboard_metrics(current_user: User = Depends(get_current_active_user)):
    try:
        metrics = get_key_metrics()
        trend = get_revenue_trend()
        income_trend = get_income_trend()
        return {**metrics, "trend": trend, "income_trend": income_trend}
    except Exception as e:
        import traceback
        with open("debug_error.log", "w") as f:
            f.write(str(e))
            f.write("\n")
            traceback.print_exc(file=f)
        raise HTTPException(status_code=500, detail=str(e))

from api.auth import get_admin_user

@app.get("/api/users")
async def list_users(current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users

from pydantic import BaseModel
class UserCreate(BaseModel):
    username: str
    password: str = None # Optional for edit
    role: str

@app.post("/api/users")
async def create_user(user: UserCreate, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    if not user.password:
        raise HTTPException(status_code=400, detail="Password required for new user")
        
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, password_hash=hashed_password, role=user.role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/api/users/{user_id}")
async def update_user(user_id: int, user: UserCreate, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db_user.username = user.username
    db_user.role = user.role
    if user.password:
        db_user.password_hash = get_password_hash(user.password)
        
    db.commit()
    return db_user

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(db_user)
    db.commit()
    return {"ok": True}

@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.get("/health")
async def health_check():
    return {"status": "ok", "env_check": "GROQ_API_KEY" in os.environ}

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request

# Mount static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Templates
templates = Jinja2Templates(directory="frontend/templates")

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Global index for simulating live data loop
CURRENT_DATA_INDEX = 0

@app.get("/api/manager/live-data")
async def live_data(company: list[str] = Query(None), current_user: User = Depends(get_current_active_user)):
    global CURRENT_DATA_INDEX
    
    import sqlite3
    # Use absolute path for robustness
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(BASE_DIR, "data", "db", "financial_data.db")
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return {"companies": [], "error": "Database not found"}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch NetIncomeLoss and Revenues
    query = """
    SELECT s.name, n.ddate, n.tag, n.value
    FROM submissions s
    JOIN numbers n ON s.adsh = n.adsh
    WHERE n.tag IN ('NetIncomeLoss', 'Revenues')
    ORDER BY n.ddate ASC
    """
    try:
        rows = cursor.execute(query).fetchall()
    except Exception as e:
        print(f"Error fetching live data: {e}")
        rows = []
    conn.close()
    
    if not rows:
        return {"companies": []}
        
    # Group by company and date to merge Revenue/Income
    # Structure: company -> date -> {income: x, revenue: y}
    company_map = {}
    
    for row in rows:
        name = row[0]
        date = str(row[1])
        tag = row[2]
        try:
            val = float(row[3])
        except (ValueError, TypeError):
            val = 0.0
        
        if name not in company_map:
            company_map[name] = {}
        if date not in company_map[name]:
            company_map[name][date] = {"income": 0, "revenue": 0}
            
        if tag == 'NetIncomeLoss':
            company_map[name][date]["income"] = val
        elif tag == 'Revenues':
            company_map[name][date]["revenue"] = val
            
    # Flatten to a single global timeline
    timeline = []
    for name, dates_dict in company_map.items():
        for d, metrics in dates_dict.items():
            inc = metrics["income"]
            rev = metrics["revenue"]
            margin = 0
            if rev != 0:
                try:
                    margin = (inc / rev) * 100
                    # Sanitize for JSON (handle Infinity/NaN)
                    import math
                    if math.isinf(margin) or math.isnan(margin):
                        margin = 0.0
                except (OverflowError, ValueError):
                    margin = 0.0
            
            timeline.append({
                "name": name,
                "period": d,
                "net_income": inc,
                "revenue": rev,
                "margin": round(margin, 2),
                "is_profit": inc > 0
            })
    
    # Filter by companies (OR logic)
    if company:
        # Normalize search terms
        search_terms = [c.lower() for c in company if c.strip()]
        if search_terms:
            timeline = [
                t for t in timeline 
                if any(term in t["name"].lower() for term in search_terms)
            ]

    # Sort by period (date) to simulate a consistent timeline
    timeline.sort(key=lambda x: str(x["period"]))
    
    if not timeline:
        return {"companies": []}

    # Verify bounds
    total_points = len(timeline)
    
    # Return a batch of 5 items so the frontend can rotate smoothly
    batch_size = 5
    response_data = []
    
    for i in range(batch_size):
        idx = (CURRENT_DATA_INDEX + i) % total_points
        item = timeline[idx]
        
        response_data.append({
            "name": item["name"],
            "period": item["period"],
            "net_income": f"{item['net_income']:,}",
            "revenue": f"{item['revenue']:,}",
            "margin": f"{item['margin']}%",
            "is_profit": item["is_profit"],
            "status": "PROFIT" if item["is_profit"] else "LOSS"
        })
        
    # Increment global index
    CURRENT_DATA_INDEX = (CURRENT_DATA_INDEX + batch_size) % total_points
    
    return {"companies": response_data}

@app.get("/api/companies/search")
async def search_companies(q: str = "", current_user: User = Depends(get_current_active_user)):
    if not q:
        return {"companies": []}
        
    import sqlite3
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(BASE_DIR, "data", "db", "financial_data.db")
    
    if not os.path.exists(db_path):
        return {"companies": []}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Case insensitive search
        query = "SELECT DISTINCT name FROM submissions WHERE name LIKE ? ORDER BY length(name) ASC, name ASC LIMIT 10"
        rows = cursor.execute(query, (f"%{q}%",)).fetchall()
        companies = [row[0] for row in rows]
    except Exception as e:
        print(f"Search error: {e}")
        companies = []
    finally:
        conn.close()
        
    return {"companies": companies}

@app.get("/manager", response_class=HTMLResponse)
async def manager_dashboard(request: Request):
    return templates.TemplateResponse("manager_dashboard.html", {
        "request": request, 
        "active_page": "dashboard"
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "active_page": "admin"
    })
@app.get("/manager/analytics", response_class=HTMLResponse)
async def manager_analytics(request: Request):
    return templates.TemplateResponse("manager_analytics.html", {
        "request": request,
        "active_page": "analytics"
    })

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
# Forced reload
