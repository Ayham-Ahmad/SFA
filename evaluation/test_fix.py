"""Quick test of the fixed evaluator"""
import sys
sys.path.insert(0, '.')

from evaluation.sfa_evaluator_v2 import SFAEvaluatorV2

e = SFAEvaluatorV2()
r = e.evaluate_query('What was the total revenue in 2024?', to_CSV=False)

print("\n" + "="*60)
print("FIX VERIFICATION")
print("="*60)
print(f"Tool Extracted: {r.extracted_tool}")
print(f"Tool Accuracy:  {r.tool_accuracy}")
print(f"SQL Found:      {r.generated_sql[:80] if r.generated_sql else 'None'}")
print(f"SQL Validity:   {r.sql_validity}")
print(f"Value Accuracy: {r.value_accuracy}")
print(f"Semantic:       {r.semantic_similarity:.3f}")
print(f"Overall:        {r.overall_score:.3f}")
print(f"Passed:         {r.passed}")
print("="*60)
