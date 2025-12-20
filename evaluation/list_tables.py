"""List all tables"""
import sqlite3
conn = sqlite3.connect('data/db/financial_data.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
for t in sorted(tables):
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cursor.fetchone()[0]
    print(f"{t}: {count:,}")
conn.close()
