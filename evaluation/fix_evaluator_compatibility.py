"""
Fix golden dataset compatibility with SFA Evaluator v2.
Updates validation_type and golden_value fields to match evaluator logic.
"""
import json

def fix_dataset():
    with open('evaluation/sfa_golden_dataset_v2.json', 'r') as f:
        data = json.load(f)
    
    # Classification of query types
    graph_ids = range(21, 31)  # 21-30
    comparison_ids = [11, 12, 13, 14, 16, 18, 20, 33, 35]
    mixed_complex_ids = [31, 32, 34]
    advisory_ids = range(36, 41) # 36-40
    
    updated_count = 0
    
    for entry in data:
        qid = entry['id']
        
        # 1. Graph Queries -> graph_exists
        if qid in graph_ids:
            entry['validation_type'] = 'graph_exists'
            # golden_value doesn't matter for graph_exists, but keeping description is fine
            if isinstance(entry.get('golden_value'), dict):
               entry['golden_value'] = "Graph data expected"
            print(f"ID {qid}: Set to graph_exists")
            updated_count += 1
            
        # 2. Comparison/Complex -> semantic
        elif qid in comparison_ids or qid in mixed_complex_ids:
            entry['validation_type'] = 'semantic'
            # Evaluator crashes on dict golden_value for numeric, so leave comparison to semantic
            if isinstance(entry.get('golden_value'), dict):
                # Convert dict to string representation for potential future use, 
                # but semantic validation primarily checks text similarity.
                entry['golden_value'] = str(entry['golden_value']) 
            print(f"ID {qid}: Set to semantic (complex/multi-value)")
            updated_count += 1
            
        # 3. Advisory -> semantic
        elif qid in advisory_ids:
            entry['validation_type'] = 'semantic'
            print(f"ID {qid}: Set to semantic (advisory)")
            updated_count += 1
            
        # 4. Numeric -> Ensure single number (already correct for 1-10, 15, 17, 19)
        else:
            if not isinstance(entry.get('golden_value'), (int, float)) and entry.get('golden_value') is not None:
                 print(f"WARNING: ID {qid} is numeric but has non-numeric value: {entry.get('golden_value')}")
    
    with open('evaluation/sfa_golden_dataset_v2.json', 'w') as f:
        json.dump(data, f, indent=4)
        
    print(f"\nFixed {updated_count} entries.")

if __name__ == "__main__":
    fix_dataset()
