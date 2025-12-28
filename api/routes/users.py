"""
User Management Routes
=======================
Admin-only endpoints for user CRUD operations.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.db_session import get_db
from api.models import User
from api.schemas import UserCreate
from api.auth_utils import get_admin_user, get_current_active_user, get_password_hash

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("")
async def list_users(
    current_user: User = Depends(get_admin_user), 
    db: Session = Depends(get_db)
):
    """List all users. Restricted to Admin."""
    users = db.query(User).all()
    return users


@router.post("")
async def create_user(
    user: UserCreate, 
    current_user: User = Depends(get_admin_user), 
    db: Session = Depends(get_db)
):
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


@router.put("/{user_id}")
async def update_user(
    user_id: int, 
    user: UserCreate, 
    current_user: User = Depends(get_admin_user), 
    db: Session = Depends(get_db)
):
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
    db.refresh(db_user)
    return db_user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int, 
    current_user: User = Depends(get_admin_user), 
    db: Session = Depends(get_db)
):
    """Delete a user. Restricted to Admin."""
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(db_user)
    db.commit()
    return {"ok": True}



