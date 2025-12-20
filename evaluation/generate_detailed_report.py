"""
Generate detailed evaluation report CSV combining:
- Golden dataset (expected answers)
- Batch results (scores)
- Analysis of what went wrong for failures
"""
import json
import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load golden dataset
with open(os.path.join(BASE_DIR, "sfa_golden_dataset.json"), 'r', encoding='utf-8') as f:
    golden = json.load(f)

# Load batch results
batch_results = []
with open(os.path.join(BASE_DIR, "batch_evaluation_20251219_215331.csv"), 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    batch_results = list(reader)

# Create detailed report
output_path = os.path.join(BASE_DIR, "evaluation_detailed_report.csv")

with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    
    # Header
    writer.writerow([
        "ID", "Query", "Category", "Difficulty",
        "Expected_Tool", "Expected_Answer", "Golden_Value",
        "Tool_Acc", "SQL_Valid", "Value_Acc", "Semantic", "Overall",
        "Passed", "Failure_Reason"
    ])
    
    for g, r in zip(golden, batch_results):
        # Determine failure reason
        passed = r['Passed'] == 'True'
        failure_reason = ""
        
        if not passed:
            tool_acc = float(r['Tool_Accuracy'])
            sql_valid = float(r['SQL_Validity'])
            value_acc = float(r['Value_Accuracy'])
            semantic = float(r['Semantic_Similarity'])
            
            if tool_acc < 1.0:
                failure_reason = f"Wrong Tool (expected {g.get('golden_tool', 'SQL')})"
            elif sql_valid < 1.0:
                failure_reason = "SQL Execution Failed"
            elif value_acc < 0.5:
                if g.get('validation_type') == 'refusal':
                    failure_reason = "Did not properly refuse/clarify"
                elif g.get('validation_type') == 'numeric':
                    failure_reason = f"Wrong Value (expected {g.get('golden_value', 'N/A')})"
                else:
                    failure_reason = "Response quality issue"
            elif semantic < 0.5:
                failure_reason = "Low semantic match to expected answer"
            else:
                failure_reason = "Threshold not met (score < 0.6)"
        
        writer.writerow([
            g.get('id', r['Query_ID']),
            g.get('query', r['Query']),
            g.get('category', r['Category']),
            g.get('difficulty', r['Difficulty']),
            g.get('golden_tool', 'SQL'),
            g.get('golden_answer', '')[:100] + "..." if len(g.get('golden_answer', '')) > 100 else g.get('golden_answer', ''),
            g.get('golden_value', ''),
            r['Tool_Accuracy'],
            r['SQL_Validity'],
            r['Value_Accuracy'],
            r['Semantic_Similarity'],
            r['Overall_Score'],
            r['Passed'],
            failure_reason
        ])

print(f"✅ Detailed report saved to: {output_path}")
print(f"\nSummary:")
print(f"Total: {len(golden)} queries")
passed_count = sum(1 for r in batch_results if r['Passed'] == 'True')
print(f"Passed: {passed_count} ({100*passed_count/len(golden):.1f}%)")
print(f"Failed: {len(golden) - passed_count} ({100*(len(golden)-passed_count)/len(golden):.1f}%)")

# Show failures
print("\n" + "="*60)
print("DETAILED FAILURE ANALYSIS")
print("="*60)

for g, r in zip(golden, batch_results):
    if r['Passed'] != 'True':
        tool_acc = float(r['Tool_Accuracy'])
        sql_valid = float(r['SQL_Validity'])
        value_acc = float(r['Value_Accuracy'])
        
        reason = ""
        if tool_acc < 1.0:
            reason = f"Wrong Tool (expected {g.get('golden_tool', 'SQL')})"
        elif sql_valid < 1.0:
            reason = "SQL Failed"
        elif value_acc < 0.5:
            reason = f"Wrong Value (expected {g.get('golden_value', g.get('golden_answer', 'N/A')[:50])})"
        else:
            reason = "Threshold not met"
            
        print(f"\n❌ [{g['id']}] {g['query'][:50]}...")
        print(f"   Expected: {g.get('golden_answer', 'N/A')[:60]}...")
        print(f"   Reason: {reason}")
        print(f"   Scores: Tool={tool_acc}, SQL={sql_valid}, Value={value_acc:.2f}, Overall={r['Overall_Score']}")
