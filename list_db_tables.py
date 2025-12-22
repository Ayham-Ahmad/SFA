import sqlite3
import os

def get_table_info(db_path):
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    info = []
    for t in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            # Get table schema to see if it's a temp table
            cursor.execute(f"PRAGMA table_info({t})")
            cols = len(cursor.fetchall())
            info.append({"name": t, "count": count, "cols": cols})
        except:
            info.append({"name": t, "count": "Error", "cols": "Error"})
            
    conn.close()
    return info

print("DATABASE: financial_data.db")
for item in get_table_info("data/db/financial_data.db"):
    print(f" - {item['name']:25} | Rows: {str(item['count']):>8} | Cols: {item['cols']}")

print("\nDATABASE: users_accounts_data.db")
for item in get_table_info("data/db/users_accounts_data.db"):
    print(f" - {item['name']:25} | Rows: {str(item['count']):>8} | Cols: {item['cols']}")
