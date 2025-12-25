import logging
import os
import json
import pathlib
import time
from datetime import datetime
from typing import Any, List, Dict

# Define paths
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
DEBUG_DIR = _PROJECT_ROOT / "debug"
SYSTEM_LOG_PATH = DEBUG_DIR / "system.log"
AGENT_LOG_PATH = DEBUG_DIR / "chatbot_debug.json"

# Ensure debug directory exists
os.makedirs(DEBUG_DIR, exist_ok=True)

# --- System Logger (Normal Logs) ---
# This logger captures application flows, errors, and general info.
system_logger = logging.getLogger("sfa_system")
system_logger.setLevel(logging.DEBUG)

# Clear existing handlers to prevent duplicates if module is reloaded
if system_logger.hasHandlers():
    system_logger.handlers.clear()

# File Handler
sys_file_handler = logging.FileHandler(SYSTEM_LOG_PATH, encoding='utf-8')
sys_file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'))
system_logger.addHandler(sys_file_handler)

# Console Handler
sys_console_handler = logging.StreamHandler()
sys_console_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
system_logger.addHandler(sys_console_handler)

def log_system_debug(message: str):
    """Logs a debug message to system.log"""
    system_logger.debug(message)

def log_system_info(message: str):
    """Logs an info message to system.log"""
    system_logger.info(message)

def log_system_error(message: str):
    """Logs an error message to system.log"""
    system_logger.error(message)

# --- Agent Logger (Structured Chatbot Debugging) ---
def log_agent_interaction(interaction_id: str, agent_name: str, task: str, input_data: Any, output_data: Any):
    """
    Logs an agent interaction to the chatbot_debug.json file.
    Maintains the structure of the previous debugger for compatibility.
    
    Args:
        interaction_id: Unique session ID.
        agent_name: Name of the agent (Planner, Worker, Auditor, etc.)
        task: Description of the task or step type.
        input_data: The input prompt or data received.
        output_data: The output generated.
    """
    
    # Prettify content if it's a string with newlines
    if isinstance(input_data, str) and "\n" in input_data:
        try:
             # Try to see if it's JSON first
            input_data = json.loads(input_data)
        except json.JSONDecodeError:
            input_data = input_data.split("\n")
            
    if isinstance(output_data, str) and "\n" in output_data:
        try:
            # Try to see if it's JSON first
            output_data = json.loads(output_data)
        except json.JSONDecodeError:
             output_data = output_data.split("\n")

    step_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "task": task,
        "input": input_data,
        "output": output_data
    }
    
    # Read-Modify-Write cycle
    logs = []
    
    # Retry logic for reading
    read_success = False
    for _ in range(3):
        try:
            if os.path.exists(AGENT_LOG_PATH):
                with open(AGENT_LOG_PATH, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        logs = json.loads(content)
            read_success = True
            break
        except (json.JSONDecodeError, PermissionError):
            time.sleep(0.1)
    
    if not read_success:
        # If read fails, simply start a new list to avoid crashing app, 
        # though this risks overwriting if it was just a lock issue.
        # Ideally we'd log this error to system log.
        system_logger.error(f"Could not read {AGENT_LOG_PATH}, starting fresh for this write.")
        logs = []

    if not isinstance(logs, list):
        logs = []

    # Update or Create Interaction
    interaction_index = -1
    for i, interaction in enumerate(logs):
        if interaction.get("interaction_id") == interaction_id:
            interaction_index = i
            break
    
    if interaction_index >= 0:
        if "steps" not in logs[interaction_index]:
             logs[interaction_index]["steps"] = []
        logs[interaction_index]["steps"].append(step_entry)
        logs[interaction_index]["last_updated"] = datetime.now().isoformat()
    else:
        new_interaction = {
            "interaction_id": interaction_id,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "steps": [step_entry]
        }
        logs.append(new_interaction)
    
    # Write back with retry
    for attempt in range(5):
        try:
            with open(AGENT_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
            break
        except PermissionError:
            time.sleep(0.2)
        except Exception as e:
            system_logger.error(f"Failed to write agent logs: {e}")
            break
