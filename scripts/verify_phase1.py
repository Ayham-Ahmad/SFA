"""Phase 1 Verification Test"""
import sqlite3

DB_PATH = "data/db/financial_data.db"

def verify_phase1():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check remaining tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    
    print("=== Phase 1 Verification ===")
    print(f"Remaining tables: {tables}")
    
    if tables == ['swf_financials']:
        print("[PASS] Only swf_financials remains")
    else:
        print(f"[WARN] Unexpected tables: {tables}")
    
    # Check row count
    cursor.execute("SELECT COUNT(*) FROM swf_financials")
    count = cursor.fetchone()[0]
    print(f"swf_financials rows: {count}")
    
    if count > 0:
        print("[PASS] Table has data")
    else:
        print("[FAIL] Table is empty")
    
    conn.close()
    print("=== Verification Complete ===")

if __name__ == "__main__":
    verify_phase1()
