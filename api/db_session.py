import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- 1. File System Setup ---
# We make sure the folder exists so the database file can be created inside it.
os.makedirs("data/db", exist_ok=True)

# --- 2. Database Configuration ---
# The address of your database file.
# Defaults to local "users_accounts_data.db" if not set in environment.
DATABASE_URL = os.getenv("ACCOUNTS_DATABASE_URL", "sqlite:///./data/db/users_accounts_data.db")

# --- 3. The Engine (The Connection Manager) ---
# This object manages the central connection to the database.
# 'check_same_thread=False' is required only for SQLite to allow multiple
# parts of your app to access the file at once.
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

# --- 4. The Session Maker (The Transaction Factory) ---
# This creates new database sessions.
# autocommit=False: We want to manually save changes (commit) only when ready.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- 5. The Model Base ---
# All your database tables (User, Account, etc.) will inherit from this class.
Base = declarative_base()

# --- 6. Dependency Helper ---
def get_db():
    """
    Opens a database session for a specific request and closes it 
    automatically when done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()