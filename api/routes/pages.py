"""
Frontend Page Routes
=====================
Serves HTML pages and static content.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from api.db_session import get_db
from api.models import User
from api.auth_utils import get_current_active_user
from backend.core.logger import log_system_error
from backend.services.ticker_service import ticker_service
from backend.services.config_service import ConfigService

router = APIRouter(tags=["Pages"])

# Setup template engine for serving HTML files
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/", response_class=HTMLResponse)
async def root():
    """Redirect root access to login page."""
    return RedirectResponse(url="/login")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the Login Page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/manager", response_class=HTMLResponse)
async def manager_dashboard(request: Request):
    """Serve Manager Dashboard HTML."""
    return templates.TemplateResponse("manager_dashboard.html", {
        "request": request, 
        "active_page": "dashboard"
    })


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Serve Admin Dashboard HTML."""
    return templates.TemplateResponse("admin_panel.html", {
        "request": request,
        "active_page": "admin"
    })


@router.get("/analytics", response_class=HTMLResponse)
async def manager_analytics(request: Request):
    """Serve Manager Analytics/Chat HTML."""
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "active_page": "analytics"
    })


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Serve unified Settings page (Theme + Database + Dashboard Config)."""
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_page": "settings"
    })


@router.get("/manager/database", response_class=HTMLResponse)
async def database_settings_page(request: Request):
    """Redirect legacy database page to unified settings."""
    return RedirectResponse(url="/settings", status_code=302)


@router.get("/api/manager/live-data")
async def live_data(current_user: User = Depends(get_current_active_user)):
    """
    Simulates a live data feed for the scrolling ticker.
    Uses TickerService to fetch and rotate data based on user config.
    """
    config = ConfigService.load_dashboard_config(current_user)
    
    # Fully dynamic fetch using the new service
    data = ticker_service.get_batch(current_user, config)
    
    refresh_interval = config.refresh_interval if config else 10
    subtitle_column = config.ticker_title_column if config else None
    
    return {
        "data": data,
        "refresh_interval": refresh_interval,
        "subtitle_column": subtitle_column
    }


@router.get("/health")
async def health_check():
    """Simple health check to verify API and Env vars are loaded."""
    import os
    return {"status": "ok", "env_check": "GROQ_API_KEY" in os.environ}
