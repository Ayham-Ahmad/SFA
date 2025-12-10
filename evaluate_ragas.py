"""
RAGAS-style Evaluation Script for Chatbot Answers
Evaluates chatbot responses against ground truth and calculates accuracy metrics.
"""
import pandas as pd
from openpyxl import Workbook
import re

# ============================================
# QUERIES AND GROUND TRUTH (DO NOT MODIFY)
# ============================================
queries = [
    "Apple revenue",
    "Microsoft revenue",
    "Apple vs Microsoft revenue",
    "Net income of Apple",
    "Total assets of Microsoft",
    "Compare Apple and Tesla revenue",
    "Top 5 companies by revenue",
    "Apple gross profit",
    "Microsoft operating income",
    "Apple cash and equivalents"
]

ground_truth = [
    "Apple Inc revenue (2025-03-31): $219.66B",
    "Microsoft Corp revenue (2025-03-31): $205.28B",
    "Apple: $219.66B, Microsoft: $205.28B. Apple has higher revenue.",
    "Apple Inc net income (2025-03-31): $93.74B",
    "Microsoft Corp total assets: $512.16B",
    "Apple: $219.66B, Tesla: $97.69B",
    "Should return list of top 5 companies sorted by revenue value descending",
    "Apple Inc gross profit: $92.96B",
    "Microsoft Corp operating income: $94.20B",
    "Apple Inc cash: $29.94B"
]

# ============================================
# PASTE YOUR CHATBOT ANSWERS HERE
# ============================================
chatbot_answers = [
    "Apple $219.66B 2025-03-31",
    "Microsoft $205.28B 2025-03-31",
    "Apple's revenue for 2025: $219.66B. Microsoft's revenue for 2025: $205.28B.",
    "Apple's net income for 2025: $61.11B.",
    "Microsoft's total assets as of March 31, 2025: $562.62B.",
    "Apple's revenue for 2025: $219.66B. Tesla's revenue for 2025: $19.34B.",
    "Data not available for this query.",
    "Apple's gross profit for 2025: $103.14B.",
    "MICROSOFT CORP $94.20B 2025-03-31",
    "Apple's cash and equivalents for 2025-03-31: $28.16B.",
]

# ============================================
# EVALUATION FUNCTIONS
# ============================================
def extract_numbers(text):
    """Extract all numerical values from text (handles $XXB, $XXM, etc.)"""
    if not text or pd.isna(text):
        return []
    text = str(text).upper()
    numbers = []
    
    # Match $219.66B patterns
    billion_matches = re.findall(r'\$?([\d,.]+)\s*B', text)
    for m in billion_matches:
        try:
            numbers.append(float(m.replace(',', '')) * 1e9)
        except:
            pass
    
    # Match $XXM patterns
    million_matches = re.findall(r'\$?([\d,.]+)\s*M', text)
    for m in million_matches:
        try:
            numbers.append(float(m.replace(',', '')) * 1e6)
        except:
            pass
    
    return numbers

def calculate_numerical_accuracy(gt, cb, tolerance=0.1):
    """Compare numerical values between ground truth and chatbot answer."""
    gt_numbers = extract_numbers(gt)
    cb_numbers = extract_numbers(cb)
    
    if not gt_numbers:
        return 1.0 if not cb_numbers else 0.5
    if not cb_numbers:
        return 0.0
    
    matches = 0
    for gt_num in gt_numbers[:2]:
        for cb_num in cb_numbers:
            ratio = min(gt_num, cb_num) / max(gt_num, cb_num) if max(gt_num, cb_num) > 0 else 0
            if ratio >= (1 - tolerance):
                matches += 1
                break
    
    return matches / len(gt_numbers[:2])

def calculate_semantic_similarity(gt, cb):
    """Simple keyword-based semantic similarity"""
    if not gt or not cb:
        return 0.0
    gt_words = set(str(gt).lower().split())
    cb_words = set(str(cb).lower().split())
    key_terms = {'apple', 'microsoft', 'tesla', 'revenue', 'income', 'assets', 'profit', 'cash'}
    gt_key = gt_words & key_terms
    cb_key = cb_words & key_terms
    if not gt_key:
        return 1.0
    return len(gt_key & cb_key) / len(gt_key)

def evaluate_answer(gt, cb):
    """Evaluate a single answer. Returns: (pass/fail, num_acc, sem_acc, overall)"""
    num_acc = calculate_numerical_accuracy(gt, cb)
    sem_acc = calculate_semantic_similarity(gt, cb)
    overall = 0.7 * num_acc + 0.3 * sem_acc
    pass_fail = "PASS" if overall >= 0.6 else "FAIL"
    return pass_fail, num_acc, sem_acc, overall

# ============================================
# RUN EVALUATION
# ============================================
print("=" * 60)
print("RAGAS EVALUATION")
print("=" * 60)

results = []
for i, (q, gt, cb) in enumerate(zip(queries, ground_truth, chatbot_answers), 1):
    pass_fail, num_acc, sem_acc, overall = evaluate_answer(gt, cb)
    results.append((pass_fail, num_acc, sem_acc, overall))
    print(f"{i}. {q}")
    print(f"   GT: {gt[:50]}...")
    print(f"   CB: {cb[:50] if cb else '(empty)'}...")
    print(f"   => {pass_fail} | Num: {num_acc:.2f} | Sem: {sem_acc:.2f} | Overall: {overall:.2f}")
    print()

# Calculate metrics
total = len(results)
passed = sum(1 for r in results if r[0] == 'PASS')
avg_num = sum(r[1] for r in results) / total
avg_sem = sum(r[2] for r in results) / total
avg_overall = sum(r[3] for r in results) / total

print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Total Queries:     {total}")
print(f"Passed:            {passed} ({passed/total*100:.1f}%)")
print(f"Failed:            {total-passed} ({(total-passed)/total*100:.1f}%)")
print(f"ACCURACY:          {passed/total*100:.1f}%")
print(f"Avg Numerical:     {avg_num:.2f}")
print(f"Avg Semantic:      {avg_sem:.2f}")
print(f"Avg Overall:       {avg_overall:.2f}")
print("=" * 60)

# Save to Excel
wb = Workbook()
ws = wb.active
ws.title = "RAGAS Evaluation"
ws.append(['Query', 'Ground Truth', 'Chatbot Answer', 'Pass/Fail', 'Num Acc', 'Sem Acc', 'Overall'])

for i, (q, gt, cb) in enumerate(zip(queries, ground_truth, chatbot_answers)):
    r = results[i]
    ws.append([q, gt, cb, r[0], f"{r[1]:.2f}", f"{r[2]:.2f}", f"{r[3]:.2f}"])

# Summary
ws.append([])
ws.append(['SUMMARY'])
ws.append(['Accuracy', f"{passed/total*100:.1f}%"])
ws.append(['Avg Numerical Acc', f"{avg_num:.2f}"])
ws.append(['Avg Semantic Acc', f"{avg_sem:.2f}"])
ws.append(['Avg Overall Score', f"{avg_overall:.2f}"])

for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
    ws.column_dimensions[col].width = 20 if col in ['A', 'B', 'C'] else 12

wb.save('chatbot_test_queries.xlsx')
print("\nSaved to chatbot_test_queries.xlsx")
