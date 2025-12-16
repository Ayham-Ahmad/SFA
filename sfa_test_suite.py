"""
SFA 20-Query Test Suite (Single Run)
======================================
Tests the chatbot across all data sources:
- 5 P&L queries (swf)
- 5 Stock queries (stock_prices)
- 4 Derived metrics queries
- 4 Advisory queries
- 2 Non-financial queries

NOTE: Runs ONCE without retries (limited API calls)
"""
import sys
import os
import csv
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.routing import run_ramas_pipeline

# Test queries organized by category
TEST_QUERIES = [
    # Category 1: P&L (swf) - 5 queries
    {"id": 1, "category": "P&L", "query": "What is the total revenue for 2024?", "expected_source": "swf"},
    {"id": 2, "category": "P&L", "query": "Show me net income for the last 3 years", "expected_source": "swf"},
    {"id": 3, "category": "P&L", "query": "What was the cost of revenue in Q4 2023?", "expected_source": "swf"},
    {"id": 4, "category": "P&L", "query": "Compare revenue and gross profit for 2024", "expected_source": "swf"},
    {"id": 5, "category": "P&L", "query": "What is the operating income for 2024?", "expected_source": "swf"},
    
    # Category 2: Stock (stock_prices) - 5 queries
    {"id": 6, "category": "Stock", "query": "What was the best closing price in 2020?", "expected_source": "stock_prices"},
    {"id": 7, "category": "Stock", "query": "Show me stock volume for January 2015", "expected_source": "stock_prices"},
    {"id": 8, "category": "Stock", "query": "What was the opening price on 2020-01-15?", "expected_source": "stock_prices"},
    {"id": 9, "category": "Stock", "query": "Give me the average closing price for 2019", "expected_source": "stock_prices"},
    {"id": 10, "category": "Stock", "query": "What days had volume above 5 million in 2010?", "expected_source": "stock_prices"},
    
    # Category 3: Derived Metrics - 4 queries
    {"id": 11, "category": "Metrics", "query": "What is the gross margin for 2024?", "expected_source": "profitability_metrics"},
    {"id": 12, "category": "Metrics", "query": "Is net income growing?", "expected_source": "growth_metrics"},
    {"id": 13, "category": "Metrics", "query": "Are we on target for revenue?", "expected_source": "variance_analysis"},
    {"id": 14, "category": "Metrics", "query": "What is the operating margin trend?", "expected_source": "profitability_metrics"},
    
    # Category 4: Advisory - 4 queries
    {"id": 15, "category": "Advisory", "query": "What is the best way to improve our profit?", "expected_source": "ADVISORY"},
    {"id": 16, "category": "Advisory", "query": "Should we reduce costs?", "expected_source": "ADVISORY"},
    {"id": 17, "category": "Advisory", "query": "How can we improve our margins?", "expected_source": "ADVISORY"},
    {"id": 18, "category": "Advisory", "query": "What strategy should we use for revenue growth?", "expected_source": "ADVISORY"},
    
    # Category 5: Non-financial - 2 queries
    {"id": 19, "category": "Non-Financial", "query": "Hello, who are you?", "expected_source": "CONVERSATIONAL"},
    {"id": 20, "category": "Non-Financial", "query": "What's the weather?", "expected_source": "CONVERSATIONAL"},
]

def run_tests():
    """Run all 20 tests once and save results."""
    print("=" * 70)
    print("SFA 20-QUERY TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = []
    passed = 0
    failed = 0
    
    for test in TEST_QUERIES:
        test_id = test["id"]
        category = test["category"]
        query = test["query"]
        
        print(f"\n[{test_id:02d}/{len(TEST_QUERIES)}] {category}: {query[:50]}...")
        
        try:
            response = run_ramas_pipeline(query)
            
            # Check if response is valid (not empty, not error)
            if response and len(response) > 10 and "Error" not in response[:50]:
                status = "PASS"
                passed += 1
                print(f"   ✅ PASS ({len(response)} chars)")
            else:
                status = "FAIL"
                failed += 1
                print(f"   ❌ FAIL: {response[:80] if response else 'Empty response'}...")
                
        except Exception as e:
            status = "ERROR"
            failed += 1
            response = f"ERROR: {str(e)}"
            print(f"   ❌ ERROR: {e}")
        
        results.append({
            "id": test_id,
            "category": category,
            "query": query,
            "expected_source": test["expected_source"],
            "status": status,
            "response_preview": response[:200] if response else "N/A"
        })
    
    # Save results to CSV
    output_file = "sfa_test_results.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "query", "expected_source", "status", "response_preview"])
        writer.writeheader()
        writer.writerows(results)
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total: {len(TEST_QUERIES)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Accuracy: {passed/len(TEST_QUERIES)*100:.1f}%")
    print(f"\nResults saved to: {output_file}")
    print("=" * 70)
    
    return passed, failed

if __name__ == "__main__":
    run_tests()
