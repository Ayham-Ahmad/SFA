"""
SWF Chatbot Test Runner - 20 Queries
=====================================
Runs 20 natural language queries through the SFA chatbot,
compares to ground truth, and outputs CSV results.
"""
import sys
import os
import sqlite3
import pandas as pd
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.routing import run_ramas_pipeline

DB_PATH = 'data/db/financial_data.db'

# 20 Test Queries with Ground Truth SQL
TEST_CASES = [
    # Simple (1-5)
    {
        "query": "What is the total revenue for 2024?",
        "ground_truth_sql": "SELECT SUM(val) FROM swf WHERE item = 'Revenue' AND yr = 2024"
    },
    {
        "query": "Show me the net income for 2025",
        "ground_truth_sql": "SELECT SUM(val) FROM swf WHERE item = 'Net Income' AND yr = 2025"
    },
    {
        "query": "What are the available financial metrics?",
        "ground_truth_sql": "SELECT DISTINCT item FROM swf ORDER BY item"
    },
    {
        "query": "How many years of data do we have?",
        "ground_truth_sql": "SELECT COUNT(DISTINCT yr) FROM swf"
    },
    {
        "query": "What was the gross profit in 2023?",
        "ground_truth_sql": "SELECT SUM(val) FROM swf WHERE item = 'Gross Profit' AND yr = 2023"
    },
    
    # Moderate (6-10)
    {
        "query": "Show me quarterly revenue for 2024",
        "ground_truth_sql": "SELECT qtr, SUM(val) FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY qtr ORDER BY qtr"
    },
    {
        "query": "What is the net income trend from 2020 to 2025?",
        "ground_truth_sql": "SELECT yr, SUM(val) FROM swf WHERE item = 'Net Income' AND yr BETWEEN 2020 AND 2025 GROUP BY yr ORDER BY yr"
    },
    {
        "query": "Compare revenue and cost of revenue for 2023",
        "ground_truth_sql": "SELECT item, SUM(val) FROM swf WHERE item IN ('Revenue', 'Cost of Revenue') AND yr = 2023 GROUP BY item"
    },
    {
        "query": "Which quarters had losses in the last 10 years?",
        "ground_truth_sql": "SELECT yr, qtr, SUM(val) FROM swf WHERE item = 'Net Income' AND yr >= 2015 GROUP BY yr, qtr HAVING SUM(val) < 0"
    },
    {
        "query": "What was the operating income for Q4 2024?",
        "ground_truth_sql": "SELECT SUM(val) FROM swf WHERE item = 'Operating Income' AND yr = 2024 AND qtr = 4"
    },
    
    # Advanced (11-15)
    {
        "query": "Show the revenue growth trend from 2015 to 2025",
        "ground_truth_sql": "SELECT yr, SUM(val) FROM swf WHERE item = 'Revenue' AND yr BETWEEN 2015 AND 2025 GROUP BY yr ORDER BY yr"
    },
    {
        "query": "What is the full income statement for 2024?",
        "ground_truth_sql": "SELECT item, SUM(val) FROM swf WHERE yr = 2024 GROUP BY item ORDER BY ABS(SUM(val)) DESC"
    },
    {
        "query": "Which year had the highest net income?",
        "ground_truth_sql": "SELECT yr, SUM(val) as ni FROM swf WHERE item = 'Net Income' GROUP BY yr ORDER BY ni DESC LIMIT 1"
    },
    {
        "query": "Show weekly revenue breakdown for Q4 2024",
        "ground_truth_sql": "SELECT mo, wk, val FROM swf WHERE item = 'Revenue' AND yr = 2024 AND qtr = 4 ORDER BY mo, wk LIMIT 20"
    },
    {
        "query": "What is the average quarterly revenue for 2024?",
        "ground_truth_sql": "SELECT AVG(qtr_rev) FROM (SELECT qtr, SUM(val) as qtr_rev FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY qtr)"
    },
    
    # Complex (16-20)
    {
        "query": "Compare the average revenue of the 2010s vs 2020s",
        "ground_truth_sql": "SELECT CASE WHEN yr < 2020 THEN '2010s' ELSE '2020s' END as decade, AVG(val) FROM swf WHERE item = 'Revenue' AND yr >= 2010 GROUP BY decade"
    },
    {
        "query": "What is the total cost of revenue over all years?",
        "ground_truth_sql": "SELECT SUM(val) FROM swf WHERE item = 'Cost of Revenue'"
    },
    {
        "query": "Show the expense breakdown for 2024",
        "ground_truth_sql": "SELECT item, SUM(val) FROM swf WHERE yr = 2024 AND item IN ('Cost of Revenue', 'Operating Expenses', 'Income Tax Expense') GROUP BY item"
    },
    {
        "query": "What was the best quarter for revenue in 2024?",
        "ground_truth_sql": "SELECT qtr, SUM(val) as rev FROM swf WHERE item = 'Revenue' AND yr = 2024 GROUP BY qtr ORDER BY rev DESC LIMIT 1"
    },
    {
        "query": "Show all income before tax values for 2025",
        "ground_truth_sql": "SELECT yr, qtr, SUM(val) FROM swf WHERE item = 'Income Before Tax' AND yr = 2025 GROUP BY yr, qtr"
    }
]

def get_ground_truth(sql):
    """Execute SQL and return formatted result."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(sql, conn)
        conn.close()
        
        if df.empty:
            return "No data"
        
        # Format the result
        if len(df) == 1 and len(df.columns) == 1:
            val = df.iloc[0, 0]
            if isinstance(val, (int, float)):
                if abs(val) >= 1e9:
                    return f"${val/1e9:.2f}B"
                elif abs(val) >= 1e6:
                    return f"${val/1e6:.2f}M"
                else:
                    return f"${val:,.2f}"
            return str(val)
        else:
            # Multiple rows - return summary
            return df.to_string(index=False, max_rows=5)
    except Exception as e:
        return f"SQL Error: {e}"

def run_tests():
    print("=" * 70)
    print("SWF CHATBOT TEST - 20 Queries")
    print("=" * 70)
    
    results = []
    
    for i, test in enumerate(TEST_CASES, 1):
        query = test["query"]
        gt_sql = test["ground_truth_sql"]
        
        print(f"\n[{i}/20] {query}")
        
        # Get ground truth
        ground_truth = get_ground_truth(gt_sql)
        print(f"   Ground Truth: {ground_truth[:100]}...")
        
        # Run through chatbot
        try:
            answer = run_ramas_pipeline(query)
            answer_clean = answer.replace('\n', ' ')[:500] if answer else "ERROR"
            print(f"   SFA Answer: {answer_clean[:100]}...")
        except Exception as e:
            answer_clean = f"ERROR: {e}"
            print(f"   SFA Error: {e}")
        
        # Simple pass/fail check (if ground truth value appears in answer)
        # This is a basic check - for numbers, we check if the significant digits match
        status = "FAIL"
        if ground_truth in answer_clean:
            status = "PASS"
        elif "No data" in ground_truth and "Data not available" in answer_clean:
            status = "PASS"
        elif any(char.isdigit() for char in ground_truth):
            # Extract numbers from ground truth and check if they appear
            import re
            gt_numbers = re.findall(r'[\d,]+\.?\d*', ground_truth.replace('$', '').replace(',', ''))
            for num in gt_numbers[:3]:  # Check first 3 numbers
                if num in answer_clean.replace(',', ''):
                    status = "PASS"
                    break
        
        print(f"   Status: {status}")
        
        results.append({
            "query_num": i,
            "query": query,
            "ground_truth": ground_truth,
            "sfa_answer": answer_clean,
            "status": status
        })
        
        time.sleep(1)  # Rate limiting
    
    # Save to CSV
    print("\n" + "=" * 70)
    df = pd.DataFrame(results)
    csv_path = "swf_chatbot_test_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"Results saved to: {csv_path}")
    
    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\nSUMMARY: {passed}/20 PASSED")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
