"""
Phase 4 Verification: Test multi-source prompt updates
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("PHASE 4 VERIFICATION")
print("=" * 60)

# Test 1: Schema includes all sources
print("\n--- Schema Check ---")
from backend.tools.sql_tools import get_table_schemas, execute_sql_query

schema = get_table_schemas()
sources = ['swf', 'stock_prices', 'financial_targets', 'profitability_metrics', 'variance_analysis', 'growth_metrics']
for s in sources:
    status = "✅" if s in schema else "❌"
    print(f"{status} '{s}' in schema")

# Test 2: Execute sample queries from different sources
print("\n--- Multi-Source Query Tests ---")
test_sqls = [
    ("P&L Revenue", "SELECT yr, SUM(val) as revenue FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY yr"),
    ("Stock best close", "SELECT MAX(close) as best FROM stock_prices WHERE yr = 2020"),
    ("Gross margin", "SELECT yr, qtr, gross_margin_pct FROM profitability_metrics WHERE yr = 2024 LIMIT 4"),
    ("Revenue variance", "SELECT metric, variance_pct, status FROM variance_analysis WHERE metric = 'Revenue' ORDER BY yr DESC LIMIT 4"),
    ("Net Income growth", "SELECT yr, qtr, growth_rate_qoq, trend FROM growth_metrics WHERE item = 'Net Income' ORDER BY yr DESC LIMIT 4"),
]

for name, sql in test_sqls:
    result = execute_sql_query(sql)
    status = "✅" if "Error" not in result else "❌"
    print(f"{status} {name}: {result[:60]}...")

# Test 3: Check prompt files have multi-source content
print("\n--- Prompt File Check ---")
import backend.llm as llm_module
import backend.prompts as prompts_module

# Check if prompts contain new sources
llm_file = open("backend/llm.py", "r").read()
prompts_file = open("backend/prompts.py", "r").read()
planner_file = open("backend/agents/planner.py", "r").read()

checks = [
    ("llm.py has stock_prices", "stock_prices" in llm_file),
    ("llm.py has profitability_metrics", "profitability_metrics" in llm_file),
    ("prompts.py has stock_prices", "stock_prices" in prompts_file),
    ("prompts.py has variance_analysis", "variance_analysis" in prompts_file),
    ("planner.py has growth_metrics", "growth_metrics" in planner_file),
]

for check_name, result in checks:
    status = "✅" if result else "❌"
    print(f"{status} {check_name}")

print("\n" + "=" * 60)
print("PHASE 4 VERIFICATION COMPLETE")
print("=" * 60)
