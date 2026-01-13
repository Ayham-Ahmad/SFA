"""
Routes Package
===============
Organizes API endpoints into logical modules.
"""
from .auth import router as auth_router
from .chat import router as chat_router
from .users import router as users_router
from .me import router as me_router
from .database import router as database_router
from .config import router as config_router
from .pages import router as pages_router
from .analytics import router as analytics_router
from .upload import router as upload_router

__all__ = [
    "auth_router",
    "chat_router", 
    "users_router",
    "me_router",
    "database_router",
    "config_router",
    "pages_router",
    "analytics_router",
    "upload_router"
]

