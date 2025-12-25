from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from .database import Base
import enum
from datetime import datetime, timezone

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"

class DatabaseType(str, enum.Enum):
    """Supported external database types for multi-tenant connections."""
    NONE = "none"
    SQLITE = "sqlite"
    CSV = "csv"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    SQLSERVER = "sqlserver"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(Enum(UserRole), default=UserRole.MANAGER)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
    
    # Database connection settings (for multi-tenant SaaS)
    db_type = Column(Enum(DatabaseType), default=DatabaseType.NONE)
    db_connection_encrypted = Column(Text, nullable=True)  # Encrypted connection string/config
    db_is_connected = Column(Boolean, default=False)
class InteractionType(str, enum.Enum):
    QUERY = "query"
    GRAPH_BUTTON = "graph_button"

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String, index=True, nullable=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    interaction_type = Column(Enum(InteractionType), default=InteractionType.QUERY)
    response_time_seconds = Column(Float, default=0.0)
    # Feedback: 1 = Like, 0 = Dislike, None = No feedback
    user_feedback = Column(Integer, nullable=True, default=None)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="history")

User.history = relationship("ChatHistory", back_populates="user", cascade="all, delete-orphan")
