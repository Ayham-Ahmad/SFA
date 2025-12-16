"""
Routing LLM Classification Test V2
===================================
20 queries ordered from SIMPLE to COMPLEX.
Tests classifier difficulty progression.
"""
import sys
import os
import csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# 20 queries ordered by difficulty (simple → complex)
TEST_QUERIES = [
    # Level 1: Very Simple (1-4)
    {"query": "Hi", "expected": ["CONVERSATIONAL"], "difficulty": "Very Simple"},
    {"query": "Revenue 2024", "expected": ["DATA"], "difficulty": "Very Simple"},
    {"query": "What is profit?", "expected": ["DATA"], "difficulty": "Very Simple"},
    {"query": "Should we expand?", "expected": ["ADVISORY"], "difficulty": "Very Simple"},
    
    # Level 2: Simple (5-8)
    {"query": "Who built this system?", "expected": ["CONVERSATIONAL"], "difficulty": "Simple"},
    {"query": "Show quarterly net income for 2024", "expected": ["DATA"], "difficulty": "Simple"},
    {"query": "What is the best strategy for growth?", "expected": ["ADVISORY"], "difficulty": "Simple"},
    {"query": "How risky is our current position?", "expected": ["ADVISORY"], "difficulty": "Simple"},
    
    # Level 3: Medium (9-12)
    {"query": "What was the closing stock price on January 15, 2020?", "expected": ["DATA"], "difficulty": "Medium"},
    {"query": "Is increasing employee salaries a good idea?", "expected": ["ADVISORY"], "difficulty": "Medium"},
    {"query": "Based on revenue, should we hire more?", "expected": ["DATA", "ADVISORY"], "difficulty": "Medium"},
    {"query": "Given our margins, is expansion safe?", "expected": ["DATA", "ADVISORY"], "difficulty": "Medium"},
    
    # Level 4: Hard (13-16)
    {"query": "Analyze the trend in operating income over the last 3 years and tell me if we should cut R&D spending", "expected": ["DATA", "ADVISORY"], "difficulty": "Hard"},
    {"query": "If net income continues at current rates, what strategic investments should we prioritize?", "expected": ["DATA", "ADVISORY"], "difficulty": "Hard"},
    {"query": "Compare Q1 and Q4 performance across 2023-2024 and recommend budget allocation changes", "expected": ["DATA", "ADVISORY"], "difficulty": "Hard"},
    {"query": "Our stock volatility seems high - should we consider a buyback program based on the price history?", "expected": ["DATA", "ADVISORY"], "difficulty": "Hard"},
    
    # Level 5: Very Complex (17-20)
    {"query": "Given the company's historical revenue growth rate of approximately 15% annually and the current net margin of around 20%, should management consider an aggressive expansion into new markets, or would a conservative approach focusing on operational efficiency be more prudent?", "expected": ["DATA", "ADVISORY"], "difficulty": "Very Complex"},
    {"query": "Considering that operating expenses have increased disproportionately to revenue in recent quarters, what cost optimization strategies would you recommend, and how should we balance short-term profitability against long-term growth investments?", "expected": ["DATA", "ADVISORY"], "difficulty": "Very Complex"},
    {"query": "If we assume a 20% revenue decline in the next fiscal year due to market conditions, combined with our current fixed cost structure, what would be the impact on net income and what preemptive measures should the finance team implement?", "expected": ["DATA", "ADVISORY"], "difficulty": "Very Complex"},
    {"query": "Based on comprehensive analysis of our P&L statements, stock price performance, operating margins, and growth metrics from 2020 to 2024, provide a strategic recommendation on whether we should pursue an IPO, seek private equity investment, or maintain current ownership structure", "expected": ["DATA", "ADVISORY"], "difficulty": "Very Complex"},
]

def classify_query(query: str) -> list:
    """Run the LLM classifier on a query."""
    classification_prompt = f"""
Classify this query into ONE OR MORE labels. Return ONLY the labels, comma-separated.

LABELS:
- CONVERSATIONAL: Greetings, identity questions, non-financial chat
- DATA: Needs database lookup for numbers, metrics, trends
- ADVISORY: Needs recommendation, strategy, decision guidance

RULES:
1. If query asks for data AND wants advice based on it → return "DATA, ADVISORY"
2. If query only asks for numbers/metrics → return "DATA"
3. If query only asks for recommendation without specific data → return "ADVISORY"
4. If query is just a greeting or non-financial → return "CONVERSATIONAL"

Query: "{query}"
Labels:"""

    response = client.chat.completions.create(
        messages=[{"role": "user", "content": classification_prompt}],
        model=MODEL,
        temperature=0,
        max_tokens=20
    ).choices[0].message.content.strip().upper()
    
    labels = [l.strip() for l in response.replace(",", " ").split() 
              if l.strip() in ["CONVERSATIONAL", "DATA", "ADVISORY"]]
    
    return labels if labels else ["DATA"]

def run_test():
    print("=" * 80)
    print("ROUTING LLM CLASSIFICATION TEST V2 (Simple → Complex)")
    print("=" * 80)
    
    results = []
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        expected = set(test["expected"])
        difficulty = test["difficulty"]
        
        print(f"\n[{i:02d}/20] [{difficulty}] {query[:60]}...")
        
        try:
            actual = classify_query(query)
            actual_set = set(actual)
            is_pass = actual_set == expected
            
            if is_pass:
                status = "PASS"
                passed += 1
                print(f"   ✅ PASS: {actual}")
            else:
                status = "FAIL"
                failed += 1
                print(f"   ❌ FAIL: Got {actual}, Expected {list(expected)}")
                
        except Exception as e:
            status = "ERROR"
            actual = ["ERROR"]
            failed += 1
            print(f"   ❌ ERROR: {e}")
        
        results.append({
            "id": i,
            "difficulty": difficulty,
            "query": query,
            "expected": ", ".join(test["expected"]),
            "actual": ", ".join(actual),
            "status": status
        })
    
    accuracy = passed / len(TEST_QUERIES) * 100
    
    # Save to CSV V2
    output_file = "routing_test_results_v2.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "difficulty", "query", "expected", "actual", "status"])
        writer.writeheader()
        writer.writerows(results)
        f.write(f"\n")
        f.write(f"SUMMARY,,,Total: {len(TEST_QUERIES)},Passed: {passed},Accuracy: {accuracy:.1f}%\n")
    
    print("\n" + "=" * 80)
    print("RESULTS BY DIFFICULTY")
    print("=" * 80)
    
    for diff in ["Very Simple", "Simple", "Medium", "Hard", "Very Complex"]:
        diff_results = [r for r in results if r["difficulty"] == diff]
        diff_passed = sum(1 for r in diff_results if r["status"] == "PASS")
        print(f"{diff:15} : {diff_passed}/{len(diff_results)} passed")
    
    print(f"\nTOTAL ACCURACY: {accuracy:.1f}%")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    run_test()
