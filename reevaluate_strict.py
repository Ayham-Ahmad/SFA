"""
Re-evaluate existing test results with STRICTER rules.
Uses existing responses from test_result_v3.csv WITHOUT re-running the pipeline.
This script only applies new evaluation logic to existing data.
"""
import csv
import re

# All 40 test queries - copied here to avoid importing from test_pipeline_v3
ALL_QUERIES = [
    {"id": 1, "query": "Hello", "category": "CONVERSATIONAL"},
    {"id": 2, "query": "Who are you?", "category": "CONVERSATIONAL"},
    {"id": 3, "query": "Revenue 2024", "category": "DATA"},
    {"id": 4, "query": "Net income 2023", "category": "DATA"},
    {"id": 5, "query": "What is gross margin?", "category": "DATA"},
    {"id": 6, "query": "Stock price 2020", "category": "DATA"},
    {"id": 7, "query": "Should we expand?", "category": "ADVISORY"},
    {"id": 8, "query": "Is our profit healthy?", "category": "ADVISORY"},
    {"id": 9, "query": "Thanks for your help", "category": "CONVERSATIONAL"},
    {"id": 10, "query": "Operating expenses 2024", "category": "DATA"},
    {"id": 11, "query": "Show quarterly net income for 2024", "category": "DATA"},
    {"id": 12, "query": "Compare revenue 2023 vs 2024", "category": "DATA"},
    {"id": 13, "query": "What was the best closing price in 2019?", "category": "DATA"},
    {"id": 14, "query": "Show me operating margin trend", "category": "DATA"},
    {"id": 15, "query": "What strategy should we use for growth?", "category": "ADVISORY"},
    {"id": 16, "query": "Is it safe to invest more?", "category": "ADVISORY"},
    {"id": 17, "query": "How risky is our current position?", "category": "ADVISORY"},
    {"id": 18, "query": "What is the average stock volume in 2015?", "category": "DATA"},
    {"id": 19, "query": "Show cost of revenue trend", "category": "DATA"},
    {"id": 20, "query": "Is the company doing well financially?", "category": "ADVISORY"},
    {"id": 21, "query": "Based on revenue, should we hire more staff?", "category": "HYBRID"},
    {"id": 22, "query": "Given our margins, is expansion safe?", "category": "HYBRID"},
    {"id": 23, "query": "Is increasing employee salaries a good idea based on our profits?", "category": "HYBRID"},
    {"id": 24, "query": "What does the stock price suggest about company value?", "category": "HYBRID"},
    {"id": 25, "query": "Compare Q1 and Q4 performance for 2024", "category": "DATA"},
    {"id": 26, "query": "Should we reduce marketing spend based on current revenue?", "category": "HYBRID"},
    {"id": 27, "query": "What was the stock volatility in 2020?", "category": "DATA"},
    {"id": 28, "query": "Is our net margin sustainable?", "category": "HYBRID"},
    {"id": 29, "query": "Show revenue by quarter for last 3 years", "category": "DATA"},
    {"id": 30, "query": "Based on costs, should we outsource operations?", "category": "HYBRID"},
    {"id": 31, "query": "Analyze operating income trend over last 3 years and advise on R&D spending", "category": "HYBRID"},
    {"id": 32, "query": "If net income continues at current rates, what investments should we prioritize?", "category": "HYBRID"},
    {"id": 33, "query": "Compare Q1 and Q4 across 2023-2024 and recommend budget allocation", "category": "HYBRID"},
    {"id": 34, "query": "Our stock seems volatile - should we consider buybacks based on price history?", "category": "HYBRID"},
    {"id": 35, "query": "Given 15% revenue growth and 20% margin, should we expand aggressively or be conservative?", "category": "HYBRID"},
    {"id": 36, "query": "Operating expenses increased disproportionately - what cost optimization do you recommend?", "category": "HYBRID"},
    {"id": 37, "query": "If revenue declines 20% next quarter, what preemptive measures should we take?", "category": "HYBRID"},
    {"id": 38, "query": "Based on P&L and stock performance 2020-2024, should we pursue IPO?", "category": "HYBRID"},
    {"id": 39, "query": "Considering margins exceeding 100% in reports, how should we interpret this for salary decisions?", "category": "HYBRID"},
    {"id": 40, "query": "With extreme growth rates showing, provide strategic recommendation for next fiscal year", "category": "HYBRID"},
]

def evaluate_response_strict(response: str, category: str, query: str) -> dict:
    """Evaluate response with STRICT rules."""
    response_lower = response.lower()
    query_lower = query.lower()
    
    has_content = len(response) > 50
    is_relevant = False
    has_data_caveats = True
    uses_ranges = True
    is_hallucinated = False
    mandatory_rule_failed = False
    fail_reason = None
    
    if category == "CONVERSATIONAL":
        is_relevant = any(word in response_lower for word in ["hello", "hi", "assist", "help", "financial", "advisor", "welcome", "pleasure"])
        
    elif category == "DATA":
        has_table = "|" in response
        has_numbers = any(char in response for char in ["$", "%"]) and any(c.isdigit() for c in response)
        has_data_keywords = any(word in response_lower for word in ["revenue", "income", "margin", "price", "volume", "cost"])
        
        is_relevant = (has_table or has_numbers) and has_data_keywords
        
        # "data not available" = NOT relevant for DATA queries
        if "not available" in response_lower or "could not be retrieved" in response_lower:
            is_relevant = False
            fail_reason = "DATA query returned no relevant data"
        
        # Hallucinated volatility
        if "volatility" in query_lower and any(c.isdigit() for c in response):
            if "calculated" not in response_lower and "formula" not in response_lower and "std" not in response_lower:
                is_hallucinated = True
                fail_reason = "Hallucinated precision"
        
    elif category in ["ADVISORY", "HYBRID"]:
        has_advisory_structure = any(word in response_lower for word in ["assessment", "recommendation", "risk", "consider", "advisory"])
        is_relevant = has_advisory_structure
        
        has_data_caveats = any(word in response_lower for word in [
            "caution", "limitation", "artifact", "synthetic", "distortion", 
            "unreliable", "extreme", "anomal", "quality issue", "invalid"
        ])
        
        uses_ranges = any(word in response_lower for word in [
            "range", "approximately", "directional", "substantial", "significant", 
            "likely", "may", "could", "if", "conditional"
        ])
        
        # Check mandatory rules for >100% margins
        if "margin" in query_lower and ("100%" in query_lower or "exceeding 100" in query_lower):
            if "distortion" not in response_lower and "invalid" not in response_lower:
                if "not indicated" in response_lower or "are not" in response_lower:
                    mandatory_rule_failed = True
                    fail_reason = "Mandatory rule violated: should flag >100% margin"
        
        # Check mandatory rules for extreme growth
        if "extreme growth" in query_lower:
            if "anomal" not in response_lower and "artifact" not in response_lower and "distortion" not in response_lower:
                mandatory_rule_failed = True
                fail_reason = "Mandatory rule violated: should flag extreme growth"
    
    else:
        is_relevant = has_content
    
    # Immediate FAIL conditions
    if is_hallucinated or mandatory_rule_failed:
        return {"score": 0, "status": "FAIL", "fail_reason": fail_reason,
                "has_content": has_content, "is_relevant": is_relevant,
                "has_data_caveats": has_data_caveats, "uses_ranges": uses_ranges}
    
    if category == "DATA" and not is_relevant:
        return {"score": 25, "status": "FAIL", "fail_reason": fail_reason or "DATA query returned no relevant data",
                "has_content": has_content, "is_relevant": False,
                "has_data_caveats": has_data_caveats, "uses_ranges": uses_ranges}
    
    # Calculate score
    score = 0
    if has_content: score += 25
    if is_relevant: score += 25
    if has_data_caveats: score += 25
    if uses_ranges: score += 25
    
    # Downgrade for partial answers
    if category == "DATA" and "trend" in query_lower and response.count("|") < 5:
        score = min(score, 80)
    
    if category in ["ADVISORY", "HYBRID"] and not has_data_caveats:
        score = min(score, 70)
    
    # Determine status
    if score >= 75:
        status = "PASS"
    elif score >= 50:
        status = "PARTIAL"
    else:
        status = "FAIL"
    
    return {"score": score, "status": status, "fail_reason": fail_reason,
            "has_content": has_content, "is_relevant": is_relevant,
            "has_data_caveats": has_data_caveats, "uses_ranges": uses_ranges}

def reevaluate():
    """Re-evaluate existing results with stricter rules."""
    
    results = []
    with open("test_result_v3.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id") and row["id"].isdigit():
                results.append(row)
    
    print("=" * 70)
    print("RE-EVALUATION WITH STRICTER RULES (NO PIPELINE CALLS)")
    print("=" * 70)
    
    new_results = []
    passed = 0
    partial = 0
    failed = 0
    changes = []
    
    for row in results:
        qid = int(row["id"])
        category = row["category"]
        query = row["query"]
        response = row["response_preview"]
        old_status = row["status"]
        old_score = int(row["score"])
        
        # Re-evaluate
        eval_result = evaluate_response_strict(response, category, query)
        new_status = eval_result["status"]
        new_score = eval_result["score"]
        fail_reason = eval_result.get("fail_reason") or ""
        
        if new_status == "PASS":
            passed += 1
        elif new_status == "PARTIAL":
            partial += 1
        else:
            failed += 1
        
        if old_status != new_status:
            changes.append(f"[{qid:02d}] {old_status}→{new_status} (score: {old_score}→{new_score}) {fail_reason}")
        
        new_results.append({
            "id": qid, "category": category, "query": query,
            "response_preview": response, "score": new_score, "status": new_status,
            "fail_reason": fail_reason, "old_status": old_status, "old_score": old_score
        })
    
    # Print changes
    print("\nSTATUS CHANGES:")
    for c in changes:
        print(c)
    
    # Save
    output_file = "test_result_v4_strict.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["id", "category", "query", "response_preview", "score", "status", "fail_reason", "old_status", "old_score"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_results)
        
        total = len(new_results)
        f.write(f"\nSUMMARY,Total: {total},Passed: {passed},Partial: {partial},Failed: {failed},Accuracy: {passed/total*100:.1f}%\n")
    
    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print(f"{'='*70}")
    print(f"Passed:   {passed}")
    print(f"Partial:  {partial}")
    print(f"Failed:   {failed}")
    print(f"Accuracy: {passed/len(new_results)*100:.1f}%")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    reevaluate()
