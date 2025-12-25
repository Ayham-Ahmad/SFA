from backend.llm import run_chain_of_tables
from backend.utils.llm_client import get_model
import re
from backend.sfa_logger import log_system_debug

# Get model from centralized configuration
WORKER_MODEL = get_model("worker")


def execute_step(step: str, user=None) -> str:
    """
    Executes a single step from the plan.
    Safe, robust, and whitespace-tolerant version.
    """
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

        result = run_chain_of_tables(query, user=user, model=WORKER_MODEL)
        
        return f"SQL Execution Result:\n{result}"

    else:
        # For any other step type, attempt SQL execution as default
        log_system_debug(f"Worker defaulting to SQL for: {original_step}")
        result = run_chain_of_tables(original_step, user=user, model=WORKER_MODEL)
        return f"SQL Execution Result:\n{result}"

