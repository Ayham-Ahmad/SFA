"""
Test SWF Prompts - 10 Test Queries
===================================
Runs SQL queries through the updated prompt system to verify SWF integration.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.tools.sql_tools import execute_sql_query, get_table_schemas

# Test queries for SWF table
TEST_QUERIES = [
    "SELECT yr, qtr, SUM(val) as revenue FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY yr, qtr ORDER BY qtr",
    "SELECT yr, SUM(val) as net_income FROM swf WHERE item = 'Net Income' AND yr >= 2020 GROUP BY yr ORDER BY yr",
    "SELECT item, SUM(val) as total FROM swf WHERE item IN ('Revenue', 'Cost of Revenue') AND yr = 2023 GROUP BY item",
    "SELECT yr, qtr, mo, wk, val FROM swf WHERE item = 'Revenue' AND yr = 2024 AND qtr = 4 ORDER BY mo, wk LIMIT 10",
    "SELECT yr, qtr, SUM(val) as net_income FROM swf WHERE item = 'Net Income' GROUP BY yr, qtr HAVING SUM(val) < 0 ORDER BY yr DESC LIMIT 10",
    "SELECT COUNT(*) as total_rows FROM swf",
    "SELECT MIN(yr) as start_year, MAX(yr) as end_year FROM swf",
    "SELECT DISTINCT item FROM swf ORDER BY item",
    "SELECT yr, SUM(val) as total FROM swf WHERE item = 'Gross Profit' AND yr >= 2015 GROUP BY yr ORDER BY yr",
    "SELECT yr, qtr, AVG(val) as avg_revenue FROM swf WHERE item = 'Revenue' GROUP BY yr, qtr ORDER BY yr DESC, qtr DESC LIMIT 12"
]

def main():
    print("=" * 60)
    print("SWF PROMPT TEST - 10 Queries")
    print("=" * 60)
    
    # Show updated schema hints
    print("\n--- Schema (with SWF hints) ---")
    schema = get_table_schemas()
    if 'swf' in schema:
        print("✓ SWF table found in schema")
        # Extract SWF part
        for line in schema.split('\n\n'):
            if 'swf' in line.lower():
                print(line[:500])
    else:
        print("❌ SWF table NOT found in schema!")
    
    print("\n--- Running Test Queries ---")
    passed = 0
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/10] {query[:60]}...")
        try:
            result = execute_sql_query(query)
            if "Error" in result or "No results" in result:
                print(f"   ❌ {result[:100]}")
            else:
                # Show first few rows
                lines = result.split('\n')[:5]
                for line in lines:
                    print(f"   {line[:80]}")
                passed += 1
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"RESULT: {passed}/10 queries passed")
    print("=" * 60)

if __name__ == "__main__":
    main()
