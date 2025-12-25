"""
Database Migration Script
=========================
Adds new columns to the users table for multi-tenant database support.
"""
import sqlite3
import os

# Use the correct database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTH_DB_PATH = os.path.join(BASE_DIR, "data", "db", "users_accounts_data.db")

def migrate():
    print("Running database migration for multi-tenant support...")
    print(f"Database path: {AUTH_DB_PATH}")
    
    if not os.path.exists(AUTH_DB_PATH):
        print(f"Database file not found: {AUTH_DB_PATH}")
        return
    
    conn = sqlite3.connect(AUTH_DB_PATH)
    cursor = conn.cursor()
    
    # Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("Users table does not exist.")
        conn.close()
        return
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    print(f"Existing columns: {existing_columns}")
    
    # Add new columns if they don't exist
    new_columns = [
        ("db_type", "TEXT DEFAULT 'NONE'"),
        ("db_connection_encrypted", "TEXT"),
        ("db_is_connected", "INTEGER DEFAULT 0")
    ]
    
    for col_name, col_def in new_columns:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name}")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        else:
            print(f"Column already exists: {col_name}")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
