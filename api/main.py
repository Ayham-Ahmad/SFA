from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta
from .database import get_db, engine, Base
from .models import User, ChatHistory, InteractionType
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
from backend.security.audit_logger import AuditMiddleware
from backend.routing import run_ramas_pipeline
import time
import sqlite3
import math
import os
from backend.ticker_service import ticker_service
from api.schemas import Token, TokenData, UserCreate, UserUpdate, ChatRequest, ChatFeedbackRequest
from pydantic import BaseModel
import asyncio
from uuid import uuid4
from asyncio import CancelledError
import json
from datetime import datetime

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------

# Load environment variables from .env file
load_dotenv()

# Create all database tables defined in models.py if they don't already exist
# This uses the SQLAlchemy engine configuration from database.py
Base.metadata.create_all(bind=engine)

# Initialize the FastAPI application with metadata
app = FastAPI(title="Smart Financial Advisory (SFA)", version="1.0.0")

# -----------------------------------------------------------------------------
# Middleware Configuration
# -----------------------------------------------------------------------------

# Add CORS (Cross-Origin Resource Sharing) middleware
# This allows the frontend (potentially running on a different port/domain) to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins (for development)
    allow_credentials=True,
    allow_methods=["*"], # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# Add Audit Middleware to log all incoming requests for security purposes
app.add_middleware(AuditMiddleware)

# Global dictionary to track active queries for cancellation support
active_queries = {}

# Global dictionary to track query progress (agent status)
query_progress = {}  # {query_id: {"status": "planner"|"worker"|"auditor", "step": "details"}}

# Helper function to log cancellations to agent_debug_log.json
def _log_cancellation(query_id: str, question: str, reason: str):
    """Log query cancellations to debug file"""
    try:
        log_entry = {
            "interaction_id": query_id,
            "timestamp": datetime.utcnow().isoformat(),
            "event": "query_cancelled",
            "reason": reason,
            "question": question
        }
        
        log_path = "agent_debug_log.json"
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logs = []
        
        logs.append(log_entry)
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to log cancellation: {e}")

# Helper functions for progress tracking
def set_query_progress(query_id: str, agent: str, step: str = ""):
    """Update progress status for a query"""
    query_progress[query_id] = {"agent": agent, "step": step}

def clear_query_progress(query_id: str):
    """Remove progress tracking for completed query"""
    query_progress.pop(query_id, None)

# -----------------------------------------------------------------------------
# Authentication Endpoints
# -----------------------------------------------------------------------------

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticates a user and returns a standard JWT access token.
    Uses OAuth2 compatible 'username' and 'password' form fields.
    """
    # Query database for the user
    user = db.query(User).filter(User.username == form_data.username).first()
    
    # Verify user exists and password matches hash
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Calculate token expiration time
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) # 30 minutes, but i think should be 1 Day
    
    # Create the JWT token including the username (sub) and expiration
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Return token and user role
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


# -----------------------------------------------------------------------------
# Chat / AI Endpoints
# -----------------------------------------------------------------------------

@app.post("/chat")
async def chat_endpoint(request: ChatRequest, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Main endpoint for interacting with the AI Financial Advisor.
    Handles message history context, RAG pipeline execution, and storing history.
    """
    start_time = time.time()
    query_id = request.query_id if request.query_id else str(uuid4())
    
    # 1. Determine Interaction Type (Standard Query or Graph Request)
    itype = InteractionType.QUERY
    if request.interaction_type == "graph_button":
        itype = InteractionType.GRAPH_BUTTON

    # 2. Retrieve Chat History for Context
    # Fetching the *last two* interactions to provide conversational context to the LLM
    query_builder = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id)
    
    # Filter by session if provided to keep context tight
    if request.session_id:
         query_builder = query_builder.filter(ChatHistory.session_id == request.session_id)
         
    # Get the most recent 2 entries
    last_exchanges = query_builder.order_by(ChatHistory.timestamp.desc()).limit(2).all()

    full_context_query = request.message
    
    # 3. Inject Context
    if last_exchanges:
        # Reverse to chronological order (oldest -> newest)
        history_lines = []
        for ex in reversed(last_exchanges):
            # Strip graph data from historical answers to prevent context pollution
            # This ensures the LLM doesn't learn patterns from previous graph/no-graph responses
            answer_clean = ex.answer.split("graph_data||")[0].strip() if "graph_data||" in ex.answer else ex.answer
            history_lines.append(f"Q: {ex.question} -> A: {answer_clean}")
        
        context_str = "\n".join(history_lines)
        full_context_query = f"Context:\n{context_str}\nUser Query: {request.message}"
    
    # 4. Execute the RAG Pipeline in a cancellable async task with 2-minute timeout
    try:
        # Initialize progress tracking
        set_query_progress(query_id, "planner", "Analyzing question...")
        
        # Wrap the synchronous RAMAS pipeline in an async task
        async def run_pipeline():
            return await asyncio.to_thread(run_ramas_pipeline, full_context_query, query_id)
        
        task = asyncio.create_task(run_pipeline())
        active_queries[query_id] = task
        
        try:
            # Add 2-minute timeout (120 seconds)
            response = await asyncio.wait_for(task, timeout=120.0)
        except asyncio.TimeoutError:
            task.cancel()
            response = "Query timed out after 2 minutes. Please try a more specific question."
            # Log timeout to debug log
            _log_cancellation(query_id, request.message, "timeout")
        except CancelledError:
            response = "Query cancelled by user."
            # Log user cancellation to debug log
            _log_cancellation(query_id, request.message, "user_cancelled")
        finally:
            active_queries.pop(query_id, None)
            clear_query_progress(query_id)  # Clean up progress tracking
    
    except Exception as e:
        response = f"An error occurred: {str(e)}"
    
    # Measure processing time
    end_time = time.time()
    duration = end_time - start_time
    
    # 5. Persist the interaction to the database
    new_history = ChatHistory(
        user_id=current_user.id,
        session_id=request.session_id,
        question=request.message,
        answer=response,
        interaction_type=itype,
        response_time_seconds=duration,
        user_feedback=None # Feedback is null until user rates it
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history) # Refresh to get the auto-generated ID
    
    # Return response and the ID (so frontend can use it for feedback)
    return {"response": response, "chat_id": new_history.id, "query_id": query_id}

@app.post("/chat/cancel/{query_id}")
async def cancel_query(query_id: str, current_user: User = Depends(get_current_active_user)):
    """
    Cancel a running query by its query_id.
    """
    if query_id in active_queries:
        active_queries[query_id].cancel()
        return {"status": "cancelled", "query_id": query_id}
    return {"status": "not_found", "query_id": query_id}

@app.get("/chat/status/{query_id}")
async def get_query_status(query_id: str, current_user: User = Depends(get_current_active_user)):
    """
    Get the current status of a running query (for progress indicator).
    """
    if query_id in query_progress:
        return query_progress[query_id]
    return {"status": "unknown", "agent": "initializing"}

@app.post("/chat/feedback/{chat_id}")
async def chat_feedback(chat_id: int, feedback: str, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """
    Updates the user feedback (Like/Dislike) for a specific chat message.
    """
    # Fetch the chat entry
    chat_entry = db.query(ChatHistory).filter(ChatHistory.id == chat_id).first()
    if not chat_entry:
        raise HTTPException(status_code=404, detail="Chat entry not found")
        
    # Security: Ensure the user modifying the feedback is the one who created the chat
    if chat_entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # Update feedback based on string input
    # Stored as Integer: 1 (Like), 0 (Dislike), None (Neutral)
    if feedback.lower() == "like":
        chat_entry.user_feedback = 1
    elif feedback.lower() == "dislike":
        chat_entry.user_feedback = 0
    else:
        chat_entry.user_feedback = None
        
    db.commit()
    return {"status": "success", "feedback": chat_entry.user_feedback}

# -----------------------------------------------------------------------------
# Analytics & Dashboard Data Endpoints
# -----------------------------------------------------------------------------

from backend.analytics.metrics import get_key_metrics, get_revenue_trend, get_income_trend

@app.get("/api/dashboard/metrics")
async def dashboard_metrics(current_user: User = Depends(get_current_active_user)):
    """
    Aggregates high-level metrics for the dashboard charts.
    Fetches data using helper functions from backend.analytics.metrics.
    """
    try:
        metrics = get_key_metrics() #########################################
        trend = get_revenue_trend() #########################################
        income_trend = get_income_trend() #########################################
        return {**metrics, "trend": trend, "income_trend": income_trend}
    except Exception as e:
        # Deep logging for debug purposes if analytics fail
        import traceback
        with open("debug_error.log", "w") as f:
            f.write(str(e))
            f.write("\n")
            traceback.print_exc(file=f)
        raise HTTPException(status_code=500, detail=str(e))

# -----------------------------------------------------------------------------
# User Management Endpoints (Admin Only)
# -----------------------------------------------------------------------------

from api.auth import get_admin_user

@app.get("/api/users")
async def list_users(current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """List all users. Restricted to Admin."""
    users = db.query(User).all()
    return users

@app.post("/api/users")
async def create_user(user: UserCreate, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Create a new user. Restricted to Admin."""
    # Check if username exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    if not user.password:
        raise HTTPException(status_code=400, detail="Password required for new user")
        
    # Hash password before storage
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, password_hash=hashed_password, role=user.role)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.put("/api/users/{user_id}")
async def update_user(user_id: int, user: UserCreate, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Update existing user details. Restricted to Admin."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db_user.username = user.username
    db_user.role = user.role
    
    # Update password only if provided
    if user.password:
        db_user.password_hash = get_password_hash(user.password)
        
    db.commit()
    return db_user

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, current_user: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    """Delete a user. Restricted to Admin."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(db_user)
    db.commit()
    return {"ok": True}

@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Return the profile of the currently logged-in user.
    Used by the frontend (sidebar) to display 'Welcome, [Username]'.
    """
    return current_user

# -----------------------------------------------------------------------------
# System & Infrastructure Endpoints
# -----------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Simple health check to verify API and Env vars are loaded"""
    return {"status": "ok", "env_check": "GROQ_API_KEY" in os.environ}

# -----------------------------------------------------------------------------
# Frontend Page Serving
# -----------------------------------------------------------------------------

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request

# Mount static files (CSS, JS, Images) to /static
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Setup template engine for serving HTML files
templates = Jinja2Templates(directory="frontend/templates")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root access to login page"""
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the Login Page"""
    return templates.TemplateResponse("login.html", {"request": request})

# Global index for simulating live data loop (keeps track of ticker position)
CURRENT_DATA_INDEX = 0

@app.get("/api/manager/live-data")
async def live_data(current_user: User = Depends(get_current_active_user)):
    """
    Simulates a live data feed for the scrolling ticker.
    Uses TickerService to fetch and rotate data from swf table.
    """
    data = ticker_service.get_batch()
    return {"companies": data}

@app.get("/manager", response_class=HTMLResponse)
async def manager_dashboard(request: Request):
    """Serve Manager Dashboard HTML"""
    return templates.TemplateResponse("manager_dashboard.html", {
        "request": request, 
        "active_page": "dashboard"
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Serve Admin Dashboard HTML"""
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "active_page": "admin"
    })

@app.get("/manager/analytics", response_class=HTMLResponse)
async def manager_analytics(request: Request):
    """Serve Manager Analytics/Chat HTML"""
    return templates.TemplateResponse("manager_analytics.html", {
        "request": request,
        "active_page": "analytics"
    })

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Start the server with hot-reload enabled for development
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
# Forced reload for ensuring updates
