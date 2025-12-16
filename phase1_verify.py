"""
Phase 1 Verification: Test queries on new tables
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.tools.sql_tools import execute_sql_query, get_table_schemas

print("=" * 60)
print("PHASE 1 VERIFICATION")
print("=" * 60)

# Test 1: Schema hints
print("\n--- Schema Hints ---")
schema = get_table_schemas()
if 'stock_prices' in schema and 'financial_targets' in schema:
    print("✅ New tables found in schema")
else:
    print("❌ Missing new tables in schema")

# Test 2: Stock prices queries
print("\n--- Stock Price Queries ---")
tests = [
    ("Row count", "SELECT COUNT(*) as rows FROM stock_prices"),
    ("Date range", "SELECT MIN(date) as min_date, MAX(date) as max_date FROM stock_prices"),
    ("Best close 2020", "SELECT MAX(close) as best_close FROM stock_prices WHERE yr = 2020"),
    ("Open > 500 in 2010", "SELECT COUNT(*) as count FROM stock_prices WHERE open > 500 AND yr = 2010"),
    ("Avg volume 2015", "SELECT ROUND(AVG(volume)) as avg_volume FROM stock_prices WHERE yr = 2015"),
]

for name, sql in tests:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:80]}...")

# Test 3: Financial targets queries
print("\n--- Financial Targets Queries ---")
tests = [
    ("Row count", "SELECT COUNT(*) as rows FROM financial_targets"),
    ("Metrics", "SELECT DISTINCT metric FROM financial_targets LIMIT 5"),
    ("2024 Revenue target", "SELECT target_value FROM financial_targets WHERE yr = 2024 AND qtr = 1 AND metric = 'Revenue'"),
]

for name, sql in tests:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:80]}...")

# Test 4: Combined query (JOIN)
print("\n--- Combined Queries ---")
combined = """
SELECT s.yr, SUM(s.val) as actual, t.target_value as target
FROM swf s
LEFT JOIN financial_targets t ON s.yr = t.yr AND s.qtr = t.qtr AND s.item = t.metric
WHERE s.item = 'Revenue' AND s.yr = 2024 AND s.qtr = 1
GROUP BY s.yr
"""
result = execute_sql_query(combined)
status = "✅" if "Error" not in result else "❌"
print(f"{status} Revenue vs Target 2024 Q1: {result[:100]}...")

print("\n" + "=" * 60)
print("PHASE 1 VERIFICATION COMPLETE")
print("=" * 60)
