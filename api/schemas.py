from pydantic import BaseModel, ConfigDict
from enum import Enum
from typing import Optional

# -----------------------------------------------------------------------------
# Enums
# ----------------------------------------------------------------------------- 
# Note: Re-defining strings here for Pydantic validation if needed, 
# or we can import from models if they are pure python enums.
# For simplicity in schemas, we often use strings or simple Enums.

# -----------------------------------------------------------------------------
# User Schemas
# -----------------------------------------------------------------------------
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    username: str | None = None

class UserCreate(BaseModel):
    username: str
    password: str = None # Optional for edit operations where password might not change
    role: str = "manager"

class UserUpdate(BaseModel):
    username: str | None = None
    role: str | None = None
    password: str | None = None

# -----------------------------------------------------------------------------
# Chat Schemas
# -----------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    interaction_type: Optional[str] = "query" # "query" or "graph_button" check InteractionType
    query_id: Optional[str] = None  # Frontend-generated query ID for progress tracking

class ChatFeedbackRequest(BaseModel):
    feedback: str  # "like" or "dislike"
