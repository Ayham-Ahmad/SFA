
import os
import sys
import json
import re

# Add the project directory to sys.path
sys.path.append(os.getcwd())

from backend.routing import run_ramas_pipeline
from backend.config import TESTING

# Define the queries from ragas_evaluator.py
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

def generate_and_update():
    if not TESTING:
        print("ERROR: TESTING flag in backend/config.py must be True.")
        return

    print("--- Starting Evaluation Data Generation ---")
    
    generated_answers = []
    generated_contexts = []
    
    # 1. Run Pipeline for each query
    for i, q in enumerate(queries):
        print(f"\n[{i+1}/{len(queries)}] Processing: {q}")
        try:
            # Clear testing.json before each run to isolate the interaction
            # (Or relies on the fact that run_ramas_pipeline appends, so we just read the last entry)
            if os.path.exists("testing.json"):
                os.remove("testing.json")
                
            # Run the pipeline
            final_answer = run_ramas_pipeline(q)
            
            # Clean answer (remove newlines/excess whitespace for neat list)
            clean_answer = final_answer.replace("\n", " ").strip()
            generated_answers.append(clean_answer)
            
            # Read context from testing.json
            combined_context = []
            if os.path.exists("testing.json"):
                with open("testing.json", "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data:
                        last_interaction = data[-1]
                        steps = last_interaction.get("steps_context", [])
                        for step in steps:
                            # Combine retrieved context from all steps
                            # Typically format: "Tool Input: ... Result: ..."
                            ctx_str = f"Tool: {step.get('type')} | Input: {step.get('tool_input')} | Result: {step.get('retrieved_context')}"
                            combined_context.append(ctx_str)
            
            generated_contexts.append(combined_context)
            
        except Exception as e:
            print(f"Error processing {q}: {e}")
            generated_answers.append("Error generating answer")
            generated_contexts.append(["Error retrieving context"])

    # 2. Format lists for insertion
    # We want to format them as Python code strings
    
    answers_code = "    chatbot_answers = [\n"
    for ans in generated_answers:
        # Escape quotes
        safe_ans = ans.replace('"', '\\"')
        answers_code += f'        "{safe_ans}",\n'
    answers_code += "    ]"

    contexts_code = "    retrieved_contexts_batch = [\n"
    for ctx_list in generated_contexts:
        contexts_code += "        [\n"
        for ctx in ctx_list:
            safe_ctx = ctx.replace('"', '\\"').replace('\n', ' ') # Flatten newlines in context string
            contexts_code += f'            "{safe_ctx}",\n'
        contexts_code += "        ],\n"
    contexts_code += "    ]"

    # 3. Update ragas_evaluator.py
    target_file = "ragas_evaluator.py"
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex to replace chatbot_answers list
    # Matches `chatbot_answers = [...]` spanning multiple lines
    content = re.sub(
        r'chatbot_answers\s*=\s*\[.*?\]', 
        answers_code, 
        content, 
        flags=re.DOTALL
    )
    
    # Regex to replace retrieved_contexts_batch list
    content = re.sub(
        r'retrieved_contexts_batch\s*=\s*\[.*?\]', 
        contexts_code, 
        content, 
        flags=re.DOTALL
    )
    
    with open(target_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"\nSUCCESS: Updated {target_file} with generated answers and contexts.")

if __name__ == "__main__":
    generate_and_update()
