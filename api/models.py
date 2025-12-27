import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from .database import Base

# --- 1. The Rules (Enums) ---
# These lists define the strict options allowed in specific columns.

class UserRole(str, enum.Enum):
    """Types of users allowed in the system."""
    ADMIN = "admin"
    MANAGER = "manager"

class DatabaseType(str, enum.Enum):
    """Types of external databases a user can connect to."""
    NONE = "none"
    SQLITE = "sqlite"
    CSV = "csv"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SQLSERVER = "sqlserver"

class InteractionType(str, enum.Enum):
    """How the user interacted: typed a question or clicked a button."""
    QUERY = "query"
    GRAPH_BUTTON = "graph_button"


# --- 2. The Tables (Models) ---

class User(Base):
    """
    Represents a registered user in the system.
    """
    __tablename__ = "users"

    # Basic Info
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)  # We store the hash, not the real password
    role = Column(Enum(UserRole), default=UserRole.MANAGER)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
    
    # Multi-Tenant Settings (Connecting to their own data)
    db_type = Column(Enum(DatabaseType), default=DatabaseType.NONE)
    db_connection_encrypted = Column(Text, nullable=True)  # Securely stored credentials
    db_is_connected = Column(Boolean, default=False)

    # Link to Chat History (One User has Many Chats)
    # cascade="all, delete-orphan" means if you delete a User, their history is deleted too.
    history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")


class ChatHistory(Base):
    """
    Records a single exchange between a User and the AI.
    """
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    
    # The Link: Who asked this?
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Session Tracking (Optional, for grouping chats)
    session_id = Column(String, index=True, nullable=True)
    
    # The Conversation
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    
    # Analytics
    interaction_type = Column(Enum(InteractionType), default=InteractionType.QUERY)
    response_time_seconds = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Feedback (1 = Thumbs Up, 0 = Thumbs Down, None = No action)
    user_feedback = Column(Integer, nullable=True, default=None)

    # Link back to the User
    user = relationship("User", back_populates="history")