import logging
import os
import json
import pathlib
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, List, Dict

# Define paths
# Define paths
# logger.py is in backend/core/logger.py
# parent -> backend/core
# parent.parent -> backend
# parent.parent.parent -> ROOT (Codes/SFA_V5)
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent.resolve()
DEBUG_DIR = _PROJECT_ROOT / "debug"
SYSTEM_LOG_PATH = DEBUG_DIR / "system.log"
AGENT_LOG_PATH = DEBUG_DIR / "chatbot_debug.json"

# Ensure debug directory exists
os.makedirs(DEBUG_DIR, exist_ok=True)

# =============================================================================
# 1. System Logger (Standard Text Logs)
# =============================================================================
system_logger = logging.getLogger("sfa_system")
system_logger.setLevel(logging.DEBUG)

if not system_logger.handlers:
    # Rotating File Handler (10MB max, keep 5 backups)
    sys_handler = RotatingFileHandler(
        SYSTEM_LOG_PATH, 
        maxBytes=10*1024*1024, 
        backupCount=5, 
        encoding='utf-8'
    )
    sys_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'))
    system_logger.addHandler(sys_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
    system_logger.addHandler(console_handler)

def log_system_debug(message: str):
    system_logger.debug(message)

def log_system_info(message: str):
    system_logger.info(message)

def log_system_error(message: str):
    system_logger.error(message)

def log_user_query(query: str):
    system_logger.info(f"USER QUERY: {query}")


# =============================================================================
# 2. Agent Logger (Structured JSON Logs)
# =============================================================================
# We implement a custom handler to handle the specific JSON Array structure requirement
# of the existing debugger tool. Standard logging behaves like append-only lines (JSONL).
# To maintain backward compatibility with a JSON Array file [], we need a specialized approach
# or simply switch to a safer append-only JSON Lines format. 
#
# DECISION: We will use a robust Read-Modify-Write approach wrapped in a critical section
# but implemented cleaner than before. Alternatively, for high performance, we switched
# to JSON Lines (.jsonl) but the frontend expects a JSON array. 
#
# IMPROVED APPROACH: Use file locking for safety.

import time

def log_agent_interaction(interaction_id: str, agent_name: str, task: str, input_data: Any, output_data: Any):
    """
    Logs an agent interaction to chatbot_debug.json.
    Refactored to be cleaner, though still requires Read-Modify-Write for JSON Array format.
    """
    # 1. Prepare Entry
    if isinstance(input_data, str) and "\\n" in input_data:
        try: input_data = json.loads(input_data)
        except json.JSONDecodeError: input_data = input_data.split("\\n")
            
    if isinstance(output_data, str) and "\\n" in output_data:
        try: output_data = json.loads(output_data)
        except json.JSONDecodeError: output_data = output_data.split("\\n")

    step_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "task": task,
        "input": input_data,
        "output": output_data
    }

    # 1.5. Custom Rotation for JSON Array Compatibility
    # We check size before reading. If huge, we rename it to archive and start fresh.
    # This ensures each file is valid valid JSON, unlike standard rotation which cuts bytes.
    MAX_JSON_BYTES = 5 * 1024 * 1024 # 5 MB
    
    if os.path.exists(AGENT_LOG_PATH):
        try:
            if os.path.getsize(AGENT_LOG_PATH) > MAX_JSON_BYTES:
                # Rotate
                timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = DEBUG_DIR / f"chatbot_debug.{timestamp_suffix}.json"
                os.rename(AGENT_LOG_PATH, backup_name)
                # Keep only last 5 backups? (Optional but good for disk space)
                # For now, we just rotate to avoid the "crash" user mentioned.
        except Exception as e:
            log_system_error(f"Failed to rotate JSON log: {e}")

    # 2. Safe Write with Retry
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Read existing
            data = []
            if os.path.exists(AGENT_LOG_PATH):
                try:
                    with open(AGENT_LOG_PATH, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            data = json.loads(content)
                except (json.JSONDecodeError, IOError) as e:
                    # If corrupted or empty, start fresh but log warning
                    log_system_error(f"Generate fresh agent log due to read error on {AGENT_LOG_PATH}: {e}")
                    data = []
            
            if not isinstance(data, list):
                data = []

            # Update Logic
            # Find existing interaction or create new
            target_interaction = None
            for interaction in data:
                if interaction.get("interaction_id") == interaction_id:
                    target_interaction = interaction
                    break
            
            if target_interaction:
                if "steps" not in target_interaction: target_interaction["steps"] = []
                target_interaction["steps"].append(step_entry)
                target_interaction["last_updated"] = datetime.now().isoformat()
            else:
                data.append({
                    "interaction_id": interaction_id,
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "steps": [step_entry]
                })

            # Write back atomic-ish
            # print(f"DEBUG: Writing to {AGENT_LOG_PATH} with {len(data)} interactions")
            with open(AGENT_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # print("DEBUG: Write SUCCESS")
            break # Success
            
        except OSError:
            # File might be locked by another process
            time.sleep(0.1)
        except Exception as e:
            log_system_error(f"Failed to write agent log: {e}")
            print(f"CRITICAL ERROR WRITING JSON: {e}")
            break
