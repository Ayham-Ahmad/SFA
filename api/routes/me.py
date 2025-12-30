"""
Current User Routes
===================
Endpoints regarding the currently logged-in user profile.
"""
from fastapi import APIRouter, Depends
from api.models import User
from api.auth_utils import get_current_active_user

# Note: Prefix logic is handled in api/main.py or parent router, 
# but usually this is just "/users/me" or "/api/me".
# Based on existing usage, it was under "/users" prefix in users.py so it resulted in "/users/me"

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    Return the profile of the currently logged-in user.
    Used by the frontend (sidebar) to display 'Welcome, [Username]'.
    """
    return current_user
