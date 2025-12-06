from sqlalchemy import Column, Integer, String, DateTime, Enum
from .database import Base
import enum
from datetime import datetime, timezone

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(Enum(UserRole), default=UserRole.MANAGER)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
