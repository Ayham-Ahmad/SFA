import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- Internal Imports ---
from backend.security.audit_logger import AuditMiddleware
from .db_session import engine, Base

# --- Import Routes (The Departments) ---
from api.routes import (
    auth_router,
    chat_router,
    users_router,
    me_router,
    database_router,
    config_router,
    pages_router,
    analytics_router
)

# 1. Setup Phase
# Load passwords/settings from the .env file
load_dotenv()

# Create database tables automatically if they don't exist
Base.metadata.create_all(bind=engine)

# Initialize the App
app = FastAPI(title="Smart Financial Advisory (SFA)", version="2.0")


# 2. Security & Middleware
# Allow other websites (like your frontend) to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change "*" to your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enable the custom Audit Logger
app.add_middleware(AuditMiddleware)


# 3. Static Files (Images, CSS, JS)
# This makes the "frontend/static" folder accessible at "http://.../static"
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


# 4. Route Registration (Connecting the Departments)
app.include_router(auth_router)       # Login/Signup
app.include_router(chat_router)       # AI Chat
app.include_router(users_router)      # Admin User Management
app.include_router(me_router)         # Current User Profile
app.include_router(database_router)   # Database Tools
app.include_router(config_router)     # Dashboard Settings
app.include_router(analytics_router)  # Graphs & Charts
app.include_router(pages_router)      # HTML Pages


# 5. Start the Server
if __name__ == "__main__":
    print("Starting SFA Server...")
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)