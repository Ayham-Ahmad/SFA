import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

# We import your database connection and User model here
from .database import get_db
from .models import User

# --- Configuration ---
# Uses the system password or defaults to "supersecretkey" if none exists
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 Hours

# Setup for password hashing (keeping your original method for compatibility)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# This tells FastAPI that the token comes from the URL "/token"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Helper Functions ---

def verify_password(plain_password, hashed_password):
    """Checks if the typed password matches the saved hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Scrambles the password before saving to DB."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta=None):
    """Generates the JWT (the digital ID badge)."""
    to_encode = data.copy()
    
    # Decide when the token expires
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default to 15 minutes if no time is specified
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    
    # Create the encoded string
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# --- Dependencies (The "Bouncers") ---

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Decodes the token, finds the username, and retrieves the user from the DB.
    """
    # Define the error to raise if anything goes wrong
    auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # 1. Decode the token using our Secret Key
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 2. Get the username from the token data
        username: str = payload.get("sub")
        
        if username is None:
            raise auth_error
            
    except JWTError:
        # If the token is fake or expired
        raise auth_error

    # 3. Find the user in the database
    user = db.query(User).filter(User.username == username).first()
    
    if user is None:
        raise auth_error
        
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Returns the user if they are successfully logged in."""
    return current_user

async def get_admin_user(current_user: User = Depends(get_current_user)):
    """Checks if the logged-in user is an admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user