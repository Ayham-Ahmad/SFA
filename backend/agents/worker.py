from backend.rag_fusion.fusion import rag_fusion_search
from backend.llm import run_chain_of_tables
import re

WORKER_MODEL = "qwen/qwen3-32b"

# Global interaction ID for current session (set by routing.py)
_current_interaction_id = None

def set_interaction_id(interaction_id: str):
    """Set the current interaction ID for logging purposes."""
    global _current_interaction_id
    _current_interaction_id = interaction_id

def execute_step(step: str) -> str:
    """
    Executes a single step from the plan.
    Safe, robust, and whitespace-tolerant version.
    """
    global _current_interaction_id
    
    print(f"Worker executing step: {step}")
    original_step = step.strip()
    print(f"Worker executing original_step: {original_step}")

    # Normalize for detection (but keep original for extraction)
    step_upper = original_step.upper()
    print(f"Worker executing original_step_upper: {step_upper}")

    # Remove list numbering like "1. " or "2) "
    step_clean = re.sub(r"^\s*\d+[\.\\)]\s*", "", original_step).strip()
    print(f"Worker executing step_clean: {step_clean}")

    if step_upper.startswith("RAG:"):
        query = step_clean.split(":", 1)[1].strip()
        print(f"Worker executing RAG: {query}")

        results = rag_fusion_search(query, n_results=3)
        return "RAG Results:\n" + "\n".join([f"- {r['content']}" for r in results])

    elif step_upper.startswith("SQL:"):
        query = step_clean.split(":", 1)[1].strip()
        print(f"Worker executing SQL: {query}")

        result = run_chain_of_tables(query, model=WORKER_MODEL)
        
        return f"SQL Execution Result:\n{result}"

    else:
        return f"Unknown tool in step → '{original_step}'"
