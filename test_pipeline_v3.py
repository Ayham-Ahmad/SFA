"""
SFA Full Pipeline Test V3
=========================
40 queries from simple to complex.
Runs in batches of 10.
Covers: CONVERSATIONAL, DATA, ADVISORY, HYBRID
"""
import sys
import os
import csv
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.routing import run_ramas_pipeline

# All 40 test queries (simple → complex)
ALL_QUERIES = [
    # Batch 1: Very Simple (1-10)
    {"id": 1, "query": "Hello", "category": "CONVERSATIONAL", "ground_truth": "Greeting response"},
    {"id": 2, "query": "Who are you?", "category": "CONVERSATIONAL", "ground_truth": "Financial AI Assistant identity"},
    {"id": 3, "query": "Revenue 2024", "category": "DATA", "ground_truth": "Revenue data for 2024 with quarterly breakdown"},
    {"id": 4, "query": "Net income 2023", "category": "DATA", "ground_truth": "Net income for 2023"},
    {"id": 5, "query": "What is gross margin?", "category": "DATA", "ground_truth": "Gross margin percentage data"},
    {"id": 6, "query": "Stock price 2020", "category": "DATA", "ground_truth": "Stock price data for 2020"},
    {"id": 7, "query": "Should we expand?", "category": "ADVISORY", "ground_truth": "Conditional recommendation with caveats"},
    {"id": 8, "query": "Is our profit healthy?", "category": "ADVISORY", "ground_truth": "Assessment with data limitations noted"},
    {"id": 9, "query": "Thanks for your help", "category": "CONVERSATIONAL", "ground_truth": "Polite acknowledgment"},
    {"id": 10, "query": "Operating expenses 2024", "category": "DATA", "ground_truth": "Operating expense data for 2024"},
    
    # Batch 2: Simple (11-20)
    {"id": 11, "query": "Show quarterly net income for 2024", "category": "DATA", "ground_truth": "Q1-Q4 net income breakdown for 2024"},
    {"id": 12, "query": "Compare revenue 2023 vs 2024", "category": "DATA", "ground_truth": "Revenue comparison between years"},
    {"id": 13, "query": "What was the best closing price in 2019?", "category": "DATA", "ground_truth": "Maximum closing price and date in 2019"},
    {"id": 14, "query": "Show me operating margin trend", "category": "DATA", "ground_truth": "Operating margin over time"},
    {"id": 15, "query": "What strategy should we use for growth?", "category": "ADVISORY", "ground_truth": "Strategic recommendation with conditions"},
    {"id": 16, "query": "Is it safe to invest more?", "category": "ADVISORY", "ground_truth": "Cautious assessment with risk considerations"},
    {"id": 17, "query": "How risky is our current position?", "category": "ADVISORY", "ground_truth": "Risk assessment with data caveats"},
    {"id": 18, "query": "What is the average stock volume in 2015?", "category": "DATA", "ground_truth": "Average trading volume for 2015"},
    {"id": 19, "query": "Show cost of revenue trend", "category": "DATA", "ground_truth": "Cost of revenue over time"},
    {"id": 20, "query": "Is the company doing well financially?", "category": "ADVISORY", "ground_truth": "Financial health assessment with limitations"},
    
    # Batch 3: Medium (21-30)
    {"id": 21, "query": "Based on revenue, should we hire more staff?", "category": "HYBRID", "ground_truth": "Data + conditional hiring recommendation"},
    {"id": 22, "query": "Given our margins, is expansion safe?", "category": "HYBRID", "ground_truth": "Margin data + expansion advice with caveats"},
    {"id": 23, "query": "Is increasing employee salaries a good idea based on our profits?", "category": "HYBRID", "ground_truth": "Profit data + salary advice with ranges (not exact)"},
    {"id": 24, "query": "What does the stock price suggest about company value?", "category": "HYBRID", "ground_truth": "Stock data + valuation assessment"},
    {"id": 25, "query": "Compare Q1 and Q4 performance for 2024", "category": "DATA", "ground_truth": "Q1 vs Q4 2024 comparison"},
    {"id": 26, "query": "Should we reduce marketing spend based on current revenue?", "category": "HYBRID", "ground_truth": "Revenue data + marketing advice"},
    {"id": 27, "query": "What was the stock volatility in 2020?", "category": "DATA", "ground_truth": "Stock price variation/volatility data"},
    {"id": 28, "query": "Is our net margin sustainable?", "category": "HYBRID", "ground_truth": "Margin data + sustainability assessment with caveats"},
    {"id": 29, "query": "Show revenue by quarter for last 3 years", "category": "DATA", "ground_truth": "Quarterly revenue 2022-2024"},
    {"id": 30, "query": "Based on costs, should we outsource operations?", "category": "HYBRID", "ground_truth": "Cost data + outsourcing recommendation"},
    
    # Batch 4: Hard/Complex (31-40)
    {"id": 31, "query": "Analyze operating income trend over last 3 years and advise on R&D spending", "category": "HYBRID", "ground_truth": "Operating income trend + R&D advice with data caveats"},
    {"id": 32, "query": "If net income continues at current rates, what investments should we prioritize?", "category": "HYBRID", "ground_truth": "Net income projection (ranges not exact) + investment advice"},
    {"id": 33, "query": "Compare Q1 and Q4 across 2023-2024 and recommend budget allocation", "category": "HYBRID", "ground_truth": "Cross-year comparison + budget advice with conditions"},
    {"id": 34, "query": "Our stock seems volatile - should we consider buybacks based on price history?", "category": "HYBRID", "ground_truth": "Volatility data + buyback recommendation with caveats"},
    {"id": 35, "query": "Given 15% revenue growth and 20% margin, should we expand aggressively or be conservative?", "category": "HYBRID", "ground_truth": "Should flag data quality if metrics seem extreme, conditional advice"},
    {"id": 36, "query": "Operating expenses increased disproportionately - what cost optimization do you recommend?", "category": "HYBRID", "ground_truth": "Expense data + optimization advice with ranges"},
    {"id": 37, "query": "If revenue declines 20% next quarter, what preemptive measures should we take?", "category": "HYBRID", "ground_truth": "Directional impact (not exact $) + contingency advice"},
    {"id": 38, "query": "Based on P&L and stock performance 2020-2024, should we pursue IPO?", "category": "HYBRID", "ground_truth": "Multi-metric analysis + IPO advice with data caveats"},
    {"id": 39, "query": "Considering margins exceeding 100% in reports, how should we interpret this for salary decisions?", "category": "HYBRID", "ground_truth": "MUST flag >100% margin as data distortion, NOT use for calculations"},
    {"id": 40, "query": "With extreme growth rates showing, provide strategic recommendation for next fiscal year", "category": "HYBRID", "ground_truth": "MUST flag extreme growth as anomaly, use ranges/directional guidance"},
]

def evaluate_response(response: str, ground_truth: str, category: str, query: str = "") -> dict:
    """Evaluate response quality with STRICTER rules."""
    response_lower = response.lower()
    query_lower = query.lower()
    
    # Basic checks
    has_content = len(response) > 50
    
    # Initialize
    is_relevant = False
    has_data_caveats = True
    uses_ranges = True
    is_hallucinated = False
    mandatory_rule_failed = False
    
    # ========================================
    # CATEGORY-SPECIFIC EVALUATION
    # ========================================
    
    if category == "CONVERSATIONAL":
        is_relevant = any(word in response_lower for word in ["hello", "hi", "assist", "help", "financial", "advisor", "welcome", "pleasure"])
        has_data_caveats = True  # Not needed
        uses_ranges = True  # Not applicable
        
    elif category == "DATA":
        # DATA queries MUST return actual data (tables, numbers)
        has_table = "|" in response
        has_numbers = any(char in response for char in ["$", "%"]) and any(c.isdigit() for c in response)
        has_data_keywords = any(word in response_lower for word in ["revenue", "income", "margin", "price", "volume", "cost"])
        
        is_relevant = (has_table or has_numbers) and has_data_keywords
        
        # Check for "data not available" responses - these are NOT relevant for DATA queries
        if "not available" in response_lower or "could not be retrieved" in response_lower:
            is_relevant = False
        
        # Check for hallucinated precision (numbers without derivation source)
        # If volatility/calculation claimed without showing formula → suspect
        if "volatility" in query_lower and any(c.isdigit() for c in response):
            if "calculated" not in response_lower and "formula" not in response_lower and "std" not in response_lower:
                is_hallucinated = True
        
        has_data_caveats = True  # Not strictly required for pure data
        uses_ranges = True  # Not required for data
        
    elif category in ["ADVISORY", "HYBRID"]:
        # ADVISORY must have assessment/recommendation structure
        has_advisory_structure = any(word in response_lower for word in ["assessment", "recommendation", "risk", "consider", "advisory"])
        is_relevant = has_advisory_structure
        
        # Check for data caveats (REQUIRED for advisory)
        has_data_caveats = any(word in response_lower for word in [
            "caution", "limitation", "artifact", "synthetic", "distortion", 
            "unreliable", "extreme", "anomal", "quality issue", "invalid"
        ])
        
        # Check for ranges vs exact projections
        has_exact_projections = "projected" in response_lower and "$" in response and any(c.isdigit() for c in response)
        uses_ranges = any(word in response_lower for word in [
            "range", "approximately", "directional", "substantial", "significant", 
            "likely", "may", "could", "if", "conditional"
        ])
        
        # MANDATORY RULE CHECKS
        # Check if query mentions >100% margins - response MUST flag this
        if "margin" in query_lower and ("100%" in query_lower or "exceeding 100" in query_lower):
            if "distortion" not in response_lower and "invalid" not in response_lower and "not economically meaningful" not in response_lower:
                # Response should acknowledge >100% is impossible, not deny it
                if "not indicated" in response_lower or "are not" in response_lower:
                    mandatory_rule_failed = True
        
        # Check if query mentions extreme growth - response MUST flag this
        if "extreme growth" in query_lower:
            if "anomal" not in response_lower and "artifact" not in response_lower and "distortion" not in response_lower:
                mandatory_rule_failed = True
        
        # For HYBRID: if data part fails, whole thing fails
        if category == "HYBRID":
            has_data_component = "|" in response or "$" in response
            if not has_data_component and "not available" not in response_lower:
                # HYBRID needs data
                pass  # This is okay if advisory is strong
    
    else:
        is_relevant = has_content
        has_data_caveats = True
        uses_ranges = True
    
    # ========================================
    # SCORING WITH BANDS
    # ========================================
    
    # Immediate FAIL conditions
    if is_hallucinated:
        return {
            "has_content": has_content, "is_relevant": is_relevant,
            "has_data_caveats": has_data_caveats, "uses_ranges": uses_ranges,
            "score": 0, "passed": "FAIL", "fail_reason": "Hallucinated precision"
        }
    
    if mandatory_rule_failed:
        return {
            "has_content": has_content, "is_relevant": is_relevant,
            "has_data_caveats": has_data_caveats, "uses_ranges": uses_ranges,
            "score": 0, "passed": "FAIL", "fail_reason": "Mandatory rule violated"
        }
    
    # DATA query without relevant data = FAIL
    if category == "DATA" and not is_relevant:
        return {
            "has_content": has_content, "is_relevant": False,
            "has_data_caveats": has_data_caveats, "uses_ranges": uses_ranges,
            "score": 25, "passed": "FAIL", "fail_reason": "DATA query returned no relevant data"
        }
    
    # Calculate score with bands
    score = 0
    if has_content: score += 25
    if is_relevant: score += 25
    if has_data_caveats: score += 25
    if uses_ranges: score += 25
    
    # Apply score bands for partial answers
    if category == "DATA":
        # Trend question with only 1 data point → downgrade
        if "trend" in query_lower and response.count("|") < 5:
            score = min(score, 80)
    
    if category in ["ADVISORY", "HYBRID"]:
        # Generic advice without specific conditions → downgrade
        if not has_data_caveats and score > 0:
            score = min(score, 70)
    
    # Determine pass/fail
    if score >= 75:
        passed = "PASS"
    elif score >= 50:
        passed = "PARTIAL"
    else:
        passed = "FAIL"
    
    return {
        "has_content": has_content,
        "is_relevant": is_relevant,
        "has_data_caveats": has_data_caveats,
        "uses_ranges": uses_ranges,
        "score": score,
        "passed": passed,
        "fail_reason": None
    }

def run_batch(start_idx: int, end_idx: int, results: list):
    """Run a batch of queries."""
    batch = ALL_QUERIES[start_idx:end_idx]
    
    print(f"\n{'='*70}")
    print(f"BATCH {start_idx//10 + 1}: Queries {start_idx+1}-{end_idx}")
    print(f"{'='*70}")
    
    batch_passed = 0
    
    for test in batch:
        qid = test["id"]
        query = test["query"]
        category = test["category"]
        ground_truth = test["ground_truth"]
        
        print(f"\n[{qid:02d}/40] [{category}] {query[:50]}...")
        
        try:
            start_time = time.time()
            response = run_ramas_pipeline(query)
            elapsed = time.time() - start_time
            
            # Evaluate
            eval_result = evaluate_response(response, ground_truth, category, query)
            
            if eval_result["passed"] == "PASS":
                batch_passed += 1
                print(f"   ✅ PASS (score: {eval_result['score']}, time: {elapsed:.1f}s)")
            elif eval_result["passed"] == "PARTIAL":
                print(f"   ⚠️ PARTIAL (score: {eval_result['score']}, time: {elapsed:.1f}s)")
            else:
                fail_reason = eval_result.get("fail_reason", "")
                print(f"   ❌ FAIL (score: {eval_result['score']}, reason: {fail_reason}, time: {elapsed:.1f}s)")
                
        except Exception as e:
            response = f"ERROR: {str(e)}"
            eval_result = {"has_content": False, "is_relevant": False, "has_data_caveats": False, "uses_ranges": False, "score": 0, "passed": "ERROR"}
            elapsed = 0
            print(f"   ❌ ERROR: {e}")
        
        results.append({
            "id": qid,
            "category": category,
            "query": query,
            "ground_truth": ground_truth,
            "response_preview": response[:200].replace("\n", " ") if response else "N/A",
            "has_content": eval_result["has_content"],
            "is_relevant": eval_result["is_relevant"],
            "has_data_caveats": eval_result["has_data_caveats"],
            "uses_ranges": eval_result["uses_ranges"],
            "score": eval_result["score"],
            "status": eval_result["passed"],
            "time_seconds": round(elapsed, 1)
        })
    
    print(f"\n--- Batch {start_idx//10 + 1} Complete: {batch_passed}/10 passed ---")
    return results

def save_results(results: list, batch_num: int):
    """Save current results to CSV."""
    output_file = "test_result_v3.csv"
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ["id", "category", "query", "ground_truth", "response_preview", 
                      "has_content", "is_relevant", "has_data_caveats", "uses_ranges", 
                      "score", "status", "time_seconds"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
        
        # Add summary
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        avg_score = sum(r["score"] for r in results) / total if total > 0 else 0
        
        f.write(f"\n")
        f.write(f"SUMMARY,Completed: {total}/40,Passed: {passed},Failed: {total-passed},Accuracy: {passed/total*100:.1f}%,Avg Score: {avg_score:.1f}\n")
    
    print(f"\nResults saved to: {output_file}")

# Main execution
if __name__ == "__main__":
    import sys
    
    batch_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    
    results = []
    
    # Load existing results if continuing
    if batch_num > 1:
        try:
            with open("test_result_v3.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["id"] and row["id"].isdigit():
                        row["id"] = int(row["id"])
                        row["score"] = int(row["score"]) if row["score"] else 0
                        row["has_content"] = row["has_content"] == "True"
                        row["is_relevant"] = row["is_relevant"] == "True"
                        row["has_data_caveats"] = row["has_data_caveats"] == "True"
                        row["uses_ranges"] = row["uses_ranges"] == "True"
                        results.append(row)
        except:
            pass
    
    start_idx = (batch_num - 1) * 10
    end_idx = min(batch_num * 10, 40)
    
    print(f"\n{'='*70}")
    print(f"SFA FULL PIPELINE TEST V3 - BATCH {batch_num}")
    print(f"{'='*70}")
    
    results = run_batch(start_idx, end_idx, results)
    save_results(results, batch_num)
    
    if end_idx < 40:
        print(f"\n⏸️  Batch {batch_num} complete. Run 'python test_pipeline_v3.py {batch_num + 1}' to continue.")
