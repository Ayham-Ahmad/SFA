"""
Phase 2 Verification: Test derived metrics views
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.tools.sql_tools import execute_sql_query, get_table_schemas

print("=" * 60)
print("PHASE 2 VERIFICATION")
print("=" * 60)

# Test 1: Schema includes views
print("\n--- Schema Check ---")
schema = get_table_schemas()
views = ['profitability_metrics', 'stock_metrics', 'variance_analysis', 'growth_metrics']
for v in views:
    status = "✅" if v in schema else "❌"
    print(f"{status} {v} in schema")

# Test 2: Profitability queries
print("\n--- Profitability Metrics ---")
tests = [
    ("Gross margin 2024", "SELECT yr, qtr, gross_margin_pct FROM profitability_metrics WHERE yr = 2024"),
    ("Net margin trend", "SELECT yr, AVG(net_margin_pct) as avg_net_margin FROM profitability_metrics WHERE yr >= 2020 GROUP BY yr"),
]
for name, sql in tests:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:60]}...")

# Test 3: Variance queries
print("\n--- Variance Analysis ---")
tests = [
    ("Revenue variance 2024", "SELECT yr, qtr, actual_value, target_value, variance_pct, status FROM variance_analysis WHERE yr = 2024 AND metric = 'Revenue'"),
    ("Over budget items", "SELECT metric, COUNT(*) as count FROM variance_analysis WHERE status = 'Over Budget' GROUP BY metric"),
]
for name, sql in tests:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:60]}...")

# Test 4: Growth queries
print("\n--- Growth Metrics ---")
tests = [
    ("Revenue growth 2024", "SELECT yr, qtr, growth_rate_qoq, trend FROM growth_metrics WHERE yr = 2024 AND item = 'Revenue'"),
    ("Declining quarters", "SELECT yr, qtr, item, growth_rate_qoq FROM growth_metrics WHERE trend = 'Declining' AND yr >= 2023 LIMIT 5"),
]
for name, sql in tests:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:60]}...")

# Test 5: Stock metrics
print("\n--- Stock Metrics ---")
tests = [
    ("Volatility 2020", "SELECT date, close, intraday_volatility_pct FROM stock_metrics WHERE yr = 2020 LIMIT 5"),
    ("Monthly avg", "SELECT yr, mo, AVG(monthly_avg_close) as avg FROM stock_metrics WHERE yr = 2020 GROUP BY yr, mo LIMIT 3"),
]
for name, sql in tests:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:60]}...")

print("\n" + "=" * 60)
print("PHASE 2 VERIFICATION COMPLETE")
print("=" * 60)
