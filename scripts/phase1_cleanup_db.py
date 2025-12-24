"""
Database Cleanup Script - Phase 1
Keep only swf_financials, drop everything else.
"""
import sqlite3
import os

DB_PATH = "data/db/financial_data.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables and views
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name")
    all_items = cursor.fetchall()
    
    print("Current database objects:")
    for name, type_ in all_items:
        print(f"  {type_.upper()}: {name}")
    
    # Keep only swf_financials
    keep_table = "swf_financials"
    
    # First drop views (they may depend on tables)
    views_to_drop = [name for name, type_ in all_items if type_ == 'view']
    for view in views_to_drop:
        print(f"\nDropping VIEW: {view}")
        cursor.execute(f"DROP VIEW IF EXISTS {view}")
    
    # Then drop tables (except swf_financials)
    tables_to_drop = [name for name, type_ in all_items if type_ == 'table' and name != keep_table]
    for table in tables_to_drop:
        print(f"Dropping TABLE: {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    
    conn.commit()
    
    # Verify
    cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')")
    remaining = cursor.fetchall()
    
    print("\n" + "="*50)
    print("Remaining database objects:")
    for name, type_ in remaining:
        print(f"  {type_.upper()}: {name}")
    
    if len(remaining) == 1 and remaining[0][0] == keep_table:
        print(f"\n✓ SUCCESS: Only '{keep_table}' remains!")
    else:
        print(f"\n⚠ WARNING: Unexpected objects remain")
    
    conn.close()

if __name__ == "__main__":
    main()
