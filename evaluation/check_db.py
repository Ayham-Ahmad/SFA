"""Detailed check of all raw SEC tables in DB"""
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/db/financial_data.db')

# Full table list
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]
print("=" * 60)
print("ALL TABLES:")
print("=" * 60)
for t in sorted(tables):
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    count = cursor.fetchone()[0]
    print(f"  {t}: {count:,} rows")

# Check schemas for key SEC tables
key_tables = ['submissions', 'numbers', 'tags', 'pre', 'num', 'sub']
print("\n" + "=" * 60)
print("KEY TABLE SCHEMAS:")
print("=" * 60)

for t in key_tables:
    if t in tables:
        print(f"\n--- {t} ---")
        cursor.execute(f"PRAGMA table_info([{t}])")
        cols = cursor.fetchall()
        for c in cols:
            print(f"  {c[1]} ({c[2]})")
        # Sample
        df = pd.read_sql(f"SELECT * FROM [{t}] LIMIT 3", conn)
        print(df.to_string())

conn.close()
