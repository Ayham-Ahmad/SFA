"""
Routing LLM Classification Test
================================
Tests ONLY the intent classifier (not the full pipeline).
20 queries from simple to complex.
Single run - no retries.
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

# Test queries with expected labels (simple to complex)
TEST_QUERIES = [
    # Simple - CONVERSATIONAL (1-3)
    {"query": "Hello", "expected": ["CONVERSATIONAL"]},
    {"query": "Who are you?", "expected": ["CONVERSATIONAL"]},
    {"query": "Thanks for your help", "expected": ["CONVERSATIONAL"]},
    
    # Simple - DATA (4-7)
    {"query": "Revenue for 2024", "expected": ["DATA"]},
    {"query": "What is net income?", "expected": ["DATA"]},
    {"query": "Show me stock prices", "expected": ["DATA"]},
    {"query": "Gross margin percentage", "expected": ["DATA"]},
    
    # Simple - ADVISORY (8-11)
    {"query": "Should we expand?", "expected": ["ADVISORY"]},
    {"query": "What strategy should we use?", "expected": ["ADVISORY"]},
    {"query": "Is it safe to invest more?", "expected": ["ADVISORY"]},
    {"query": "How can we improve profitability?", "expected": ["ADVISORY"]},
    
    # Medium - HYBRID DATA+ADVISORY (12-16)
    {"query": "Based on 2024 revenue, should we expand?", "expected": ["DATA", "ADVISORY"]},
    {"query": "Is the company profitable enough to hire more staff?", "expected": ["DATA", "ADVISORY"]},
    {"query": "Given net income trends, should we increase salaries?", "expected": ["DATA", "ADVISORY"]},
    {"query": "What does the margin data suggest about our pricing strategy?", "expected": ["DATA", "ADVISORY"]},
    {"query": "Looking at last year's costs, should we cut expenses?", "expected": ["DATA", "ADVISORY"]},
    
    # Complex - HYBRID (17-20)
    {"query": "Based on the company's 2024 financial performance including revenue and net income, should employee salaries be increased next year?", "expected": ["DATA", "ADVISORY"]},
    {"query": "Analyze our stock price volatility and recommend whether we should buy back shares", "expected": ["DATA", "ADVISORY"]},
    {"query": "If revenue declined 20% next quarter, what cost reduction measures should we consider?", "expected": ["DATA", "ADVISORY"]},
    {"query": "Compare operating margins across quarters and advise on operational efficiency improvements", "expected": ["DATA", "ADVISORY"]},
]

def classify_query(query: str) -> list:
    """Run the LLM classifier on a query."""
    classification_prompt = f"""
Classify this query into ONE OR MORE labels. Return ONLY the labels, comma-separated.

LABELS:
- CONVERSATIONAL: Greetings, identity questions, non-financial chat ("Hello", "Who are you?")
- DATA: Needs database lookup for numbers, metrics, trends ("Revenue for 2024", "Net income by quarter")
- ADVISORY: Needs recommendation, strategy, decision guidance ("Should we expand?", "Is it safe to invest?")

RULES:
1. If query asks for data AND wants advice based on it → return "DATA, ADVISORY"
2. If query only asks for numbers/metrics → return "DATA"
3. If query only asks for recommendation without specific data → return "ADVISORY"
4. If query is just a greeting or non-financial → return "CONVERSATIONAL"

EXAMPLES:
"Hello" → CONVERSATIONAL
"Revenue for 2024" → DATA
"Should we increase salaries?" → ADVISORY
"Based on 2024 revenue, should we expand?" → DATA, ADVISORY
"What is net income and is it sustainable?" → DATA, ADVISORY

Query: "{query}"
Labels:"""

    response = client.chat.completions.create(
        messages=[{"role": "user", "content": classification_prompt}],
        model=MODEL,
        temperature=0,
        max_tokens=20
    ).choices[0].message.content.strip().upper()
    
    # Parse labels
    labels = [l.strip() for l in response.replace(",", " ").split() 
              if l.strip() in ["CONVERSATIONAL", "DATA", "ADVISORY"]]
    
    return labels if labels else ["DATA"]

def run_test():
    """Run the classification test."""
    print("=" * 70)
    print("ROUTING LLM CLASSIFICATION TEST (20 queries)")
    print("=" * 70)
    
    results = []
    passed = 0
    failed = 0
    
    for i, test in enumerate(TEST_QUERIES, 1):
        query = test["query"]
        expected = set(test["expected"])
        
        print(f"\n[{i:02d}/20] {query[:50]}...")
        
        try:
            actual = classify_query(query)
            actual_set = set(actual)
            
            # Check if classification is correct
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
            "query": query,
            "expected": ", ".join(test["expected"]),
            "actual": ", ".join(actual),
            "status": status
        })
    
    # Calculate accuracy
    accuracy = passed / len(TEST_QUERIES) * 100
    
    # Save to CSV
    output_file = "routing_test_results.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["id", "query", "expected", "actual", "status"])
        writer.writeheader()
        writer.writerows(results)
        
        # Add summary row
        f.write(f"\n")
        f.write(f"SUMMARY,Total: {len(TEST_QUERIES)},Passed: {passed},Failed: {failed},Accuracy: {accuracy:.1f}%\n")
    
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Total:    {len(TEST_QUERIES)}")
    print(f"Passed:   {passed}")
    print(f"Failed:   {failed}")
    print(f"Accuracy: {accuracy:.1f}%")
    print(f"\nSaved to: {output_file}")
    print("=" * 70)

if __name__ == "__main__":
    run_test()
