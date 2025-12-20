"""Check existing swf table and see if submissions/numbers need to be loaded"""
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/db/financial_data.db')

# Check swf table schema
print("=" * 60)
print("EXISTING SWF TABLE SCHEMA:")
print("=" * 60)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(swf)")
for c in cursor.fetchall():
    print(f"  {c[1]} ({c[2]})")

# Sample from swf
print("\n--- Sample from swf ---")
df = pd.read_sql("SELECT * FROM swf LIMIT 5", conn)
print(df.to_string())

# Check for numbers/submissions
print("\n" + "=" * 60)
print("Checking if raw SEC tables exist...")
print("=" * 60)

for t in ['numbers', 'submissions', 'num', 'sub']:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        print(f"  {t}: {cursor.fetchone()[0]:,} rows")
    except:
        print(f"  {t}: NOT FOUND")

# Check pre table schema (it exists)
print("\n--- PRE table schema ---")
cursor.execute("PRAGMA table_info(pre)")
for c in cursor.fetchall():
    print(f"  {c[1]} ({c[2]})")

print("\n--- PRE sample ---")
df_pre = pd.read_sql("SELECT * FROM pre LIMIT 5", conn)
print(df_pre.to_string())

conn.close()
