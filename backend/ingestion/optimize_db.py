import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")

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
