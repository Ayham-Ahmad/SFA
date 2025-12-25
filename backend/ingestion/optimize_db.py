import sqlite3
import os
from backend.utils.paths import DB_PATH

def optimize_db():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("Creating Composite Index for filtered rankings...")
    # This index matches: WHERE tag='...' AND uom='...' AND ddate BETWEEN ... ORDER BY value
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_numbers_composite 
    ON numbers(tag, uom, ddate, value)
    """)
    
    print("Running ANALYZE to update statistics...")
    cursor.execute("ANALYZE")
    
    conn.commit()
    conn.close()
    print("Optimization Complete.")

if __name__ == "__main__":
    optimize_db()
