"""Clean exploration of existing data structures"""
import sqlite3
import pandas as pd

conn = sqlite3.connect('data/db/financial_data.db')
cursor = conn.cursor()

# ============================================================
# 1. EXISTING SWF TABLE
# ============================================================
print("=" * 70)
print("1. EXISTING SWF TABLE")
print("=" * 70)
cursor.execute("PRAGMA table_info(swf)")
cols = cursor.fetchall()
print("Columns:")
for c in cols:
    print(f"  - {c[1]} ({c[2]})")

df_swf = pd.read_sql("SELECT * FROM swf LIMIT 3", conn)
print("\nSample:")
for col in df_swf.columns:
    print(f"  {col}: {df_swf[col].tolist()}")

# ============================================================
# 2. PRE TABLE (Presentation)
# ============================================================
print("\n" + "=" * 70)
print("2. PRE TABLE (Presentation)")
print("=" * 70)
cursor.execute("PRAGMA table_info(pre)")
cols = cursor.fetchall()
print("Columns:")
for c in cols:
    print(f"  - {c[1]} ({c[2]})")

df_pre = pd.read_sql("SELECT * FROM pre WHERE stmt='IS' LIMIT 3", conn)
print("\nSample (Income Statement only):")
for col in df_pre.columns:
    print(f"  {col}: {df_pre[col].tolist()}")

# ============================================================
# 3. TAGS TABLE
# ============================================================
print("\n" + "=" * 70)
print("3. TAGS TABLE")
print("=" * 70)
cursor.execute("PRAGMA table_info(tags)")
cols = cursor.fetchall()
print("Columns:")
for c in cols:
    print(f"  - {c[1]} ({c[2]})")

# ============================================================
# 4. CHECK FOR MISSING RAW TABLES
# ============================================================
print("\n" + "=" * 70)
print("4. MISSING RAW TABLES (need to load from txt files)")
print("=" * 70)

for t in ['numbers', 'submissions', 'num', 'sub']:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
        print(f"  {t}: EXISTS - {cursor.fetchone()[0]:,} rows")
    except:
        print(f"  {t}: MISSING - needs loading from raw_data/{t}.txt")

conn.close()
