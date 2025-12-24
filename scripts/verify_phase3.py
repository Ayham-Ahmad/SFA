"""Verify Phase 3 data extension"""
import sqlite3
import pandas as pd

DB_PATH = "data/db/financial_data.db"
CSV_PATH = "data/SWF.csv"

# Database verification
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM swf_financials")
total = cursor.fetchone()[0]

cursor.execute("SELECT MIN(year), MAX(year) FROM swf_financials")
min_yr, max_yr = cursor.fetchone()

cursor.execute("SELECT data_coverage_flag, COUNT(*) FROM swf_financials GROUP BY data_coverage_flag")
flags = cursor.fetchall()

print("=== Database Verification ===")
print(f"Total rows: {total}")
print(f"Year range: {min_yr} to {max_yr}")
print(f"Years covered: {max_yr - min_yr + 1}")
print("\nData by source:")
for f in flags:
    print(f"  {f[0]}: {f[1]} rows")

conn.close()

# CSV verification
print("\n=== CSV File Verification ===")
df = pd.read_csv(CSV_PATH)
print(f"CSV rows: {len(df)}")
print(f"CSV year range: {df['year'].min()} to {df['year'].max()}")

# Sample data
print("\n=== Sample Data ===")
print("First 3 rows (earliest - should be 1996):")
print(df.head(3)[['year', 'quarter', 'revenue', 'data_coverage_flag']].to_string())
print("\nLast 3 rows (latest - should be 2025):")
print(df.tail(3)[['year', 'quarter', 'revenue', 'data_coverage_flag']].to_string())
