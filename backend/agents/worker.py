from backend.llm import run_chain_of_tables
import re
from backend.sfa_logger import log_system_debug

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
    
    log_system_debug(f"Worker executing step: {step}")
    original_step = step.strip()
    
    # Normalize for detection (but keep original for extraction)
    step_upper = original_step.upper()

    # Remove list numbering like "1. " or "2) "
    step_clean = re.sub(r"^\s*\d+[\.\\)]\s*", "", original_step).strip()
    log_system_debug(f"Worker executing step_clean: {step_clean}")

    if step_upper.startswith("SQL:"):
        query = step_clean.split(":", 1)[1].strip()
        log_system_debug(f"Worker executing SQL: {query}")

        result = run_chain_of_tables(query, model=WORKER_MODEL)
        
        return f"SQL Execution Result:\n{result}"

    else:
        # For any other step type, attempt SQL execution as default
        log_system_debug(f"Worker defaulting to SQL for: {original_step}")
        result = run_chain_of_tables(original_step, model=WORKER_MODEL)
        return f"SQL Execution Result:\n{result}"

