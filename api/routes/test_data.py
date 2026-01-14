"""
Test Data API
=============
Endpoints for adding test data to simulate live financial updates.
ADMIN ONLY - for demo/testing purposes.
"""
import random
import sqlite3
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from api.auth_utils import get_current_active_user
from api.models import User, UserRole
from backend.services.tenant_manager import MultiTenantDBManager, decrypt_config
from backend.core.logger import log_system_info

router = APIRouter(prefix="/api/test", tags=["Test"])


@router.post("/add-live-data")
async def add_live_data(current_user: User = Depends(get_current_active_user)):
    """
    Add a random data point to the user's connected database.
    Uses the live_metrics table structure.
    """
    if not current_user.db_is_connected:
        raise HTTPException(status_code=400, detail="No database connected")
    
    # Get the user's database path
    try:
        config = decrypt_config(current_user.db_connection_encrypted)
        db_path = config.get("path", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot decrypt config: {e}")
    
    if not db_path:
        raise HTTPException(status_code=400, detail="No database path configured")
    
    # Generate random data
    timestamp = datetime.now().isoformat()
    revenue = round(random.uniform(5000, 15000), 2)
    cost = round(random.uniform(2000, 8000), 2)
    active_users = random.randint(100, 1000)
    efficiency = round(revenue / cost if cost > 0 else 0, 2)
    
    # Insert into database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS live_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                revenue REAL,
                cost REAL,
                active_users INTEGER,
                efficiency_score REAL
            )
        ''')
        
        cursor.execute(
            'INSERT INTO live_metrics (timestamp, revenue, cost, active_users, efficiency_score) VALUES (?, ?, ?, ?, ?)',
            (timestamp, revenue, cost, active_users, efficiency)
        )
        conn.commit()
        conn.close()
        
        log_system_info(f"[TestAPI] Added data: Rev=${revenue}, Cost=${cost}")
        
        return {
            "success": True,
            "data": {
                "timestamp": timestamp,
                "revenue": revenue,
                "cost": cost,
                "active_users": active_users,
                "efficiency_score": efficiency
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/init-users")
async def init_users_database():
    """
    Initialize the users database with a default admin user.
    WARNING: This will create tables if they don't exist and add a default admin.
    Use this only for initial Railway setup.
    """
    import os
    from backend.utils.paths import DATA_DIR
    from api.auth_utils import get_password_hash
    
    db_path = os.path.join(DATA_DIR, "users_accounts_data.db")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                role VARCHAR DEFAULT 'MANAGER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                db_is_connected BOOLEAN DEFAULT 0,
                db_connection_encrypted TEXT,
                dashboard_config_encrypted TEXT
            )
        ''')
        
        # Create chat_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role VARCHAR NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Check if admin exists
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            # Create default admin with password 'admin123'
            admin_hash = get_password_hash("admin123")
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", admin_hash, "ADMIN")
            )
        
        conn.commit()
        
        # Get user count
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "success": True,
            "message": f"Database initialized at {db_path}",
            "user_count": user_count,
            "default_admin": "admin / admin123"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Init error: {e}")


@router.get("/debug-paths")
async def debug_paths():
    """Debug endpoint to show current paths."""
    import os
    from backend.utils.paths import DATA_DIR, BACKUP_DIR
    
    db_path = os.path.join(DATA_DIR, "users_accounts_data.db")
    
    return {
        "DATA_DIR": DATA_DIR,
        "BACKUP_DIR": BACKUP_DIR,
        "db_exists": os.path.exists(db_path),
        "db_path": db_path,
        "SFA_DATA_DIR_env": os.getenv("SFA_DATA_DIR", "NOT SET"),
        "ACCOUNTS_DATABASE_URL_env": os.getenv("ACCOUNTS_DATABASE_URL", "NOT SET")
    }

