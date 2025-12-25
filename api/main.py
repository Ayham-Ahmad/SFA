"""
Smart Financial Advisory (SFA) - Main Application
===================================================
FastAPI application with modular route organization.

Routes are now split into separate modules:
- api/routes/auth.py      - Authentication
- api/routes/chat.py      - AI Chat & History
- api/routes/users.py     - User Management (Admin)
- api/routes/database.py  - Multi-tenant DB Management
- api/routes/config.py    - Dashboard Configuration
- api/routes/pages.py     - Frontend Page Serving
- api/routes/analytics.py - Dashboard Metrics
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import uvicorn
import os

from .database import engine, Base
from backend.security.audit_logger import AuditMiddleware

# Import all route modules
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

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------

# Load environment variables from .env file
load_dotenv()

# Create all database tables defined in models.py if they don't already exist
Base.metadata.create_all(bind=engine)

# Initialize the FastAPI application with metadata
app = FastAPI(title="Smart Financial Advisory (SFA)", version="1.0.0")

# -----------------------------------------------------------------------------
# Middleware Configuration
# -----------------------------------------------------------------------------

# Add CORS (Cross-Origin Resource Sharing) middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Audit Middleware to log all incoming requests
app.add_middleware(AuditMiddleware)

# -----------------------------------------------------------------------------
# Static Files Configuration
# -----------------------------------------------------------------------------

# Mount static files (CSS, JS, Images) to /static
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# -----------------------------------------------------------------------------
# Route Registration
# -----------------------------------------------------------------------------

# Authentication routes
app.include_router(auth_router)

# Chat & AI routes (prefix: /chat)
app.include_router(chat_router)

# User management routes (prefix: /api/users)
app.include_router(users_router)

# Current user endpoint (prefix: /users)
app.include_router(me_router)

# Database management routes (prefix: /api/database)
app.include_router(database_router)

# Dashboard configuration routes (prefix: /api)
app.include_router(config_router)

# Analytics routes (prefix: /api/dashboard)
app.include_router(analytics_router)

# Frontend page routes (no prefix)
app.include_router(pages_router)


# -----------------------------------------------------------------------------
# Legacy Exports for Backward Compatibility
# -----------------------------------------------------------------------------

# These are needed by chat.py for query tracking
# In a future refactor, these could be moved to a shared state module
from api.routes.chat import set_query_progress, clear_query_progress, active_queries, query_progress


# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Start the server with hot-reload enabled for development
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
