"""
Script to remove legacy tables from financial_data.db
These tables are no longer used after migrating to swf + stock_prices.
"""
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")

LEGACY_TABLES = [
    "numbers",
    "submissions",
    "annual_metrics",
    "income_statements"
]

def drop_legacy_tables():
    """Drop legacy tables that are no longer used."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # First, list all tables before
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_before = [row[0] for row in cursor.fetchall()]
    print(f"Tables BEFORE cleanup: {tables_before}")
    
    for table in LEGACY_TABLES:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"✓ Dropped table: {table}")
        except Exception as e:
            print(f"✗ Error dropping {table}: {e}")
    
    conn.commit()
    
    # List tables after
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables_after = [row[0] for row in cursor.fetchall()]
    print(f"\nTables AFTER cleanup: {tables_after}")
    
    conn.close()
    print("\n✅ Legacy table cleanup complete!")

if __name__ == "__main__":
    drop_legacy_tables()
