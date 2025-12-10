import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List

# File where all interactions will be stored (use absolute path for reliability)
import pathlib
_PROJECT_ROOT = pathlib.Path(__file__).parent.parent.resolve()
DEBUG_FILE_PATH = str(_PROJECT_ROOT / "agent_debug_log.json")

def log_agent_interaction(interaction_id: str, agent_name: str, step_type: str, input_data: Any, output_data: Any):
    """
    Logs a single step of an agent to a JSON record.
    
    Args:
        interaction_id: Unique ID for the user's query session.
        agent_name: 'Planner', 'Worker', or 'Auditor'.
        step_type: 'Input', 'Thinking', 'Tool Call', 'Output'.
        input_data: The prompt or input given to the agent.
        output_data: The response or result generated.
    """
    
    # Prettify content: duplicate newlines to make it readable in JSON
    if isinstance(input_data, str) and "\n" in input_data:
        input_data = input_data.split("\n")
    if isinstance(output_data, str) and "\n" in output_data:
        output_data = output_data.split("\n")

    step_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "step_type": step_type,
        "input": input_data,
        "output": output_data
    }
    
    # Read existing logs
    logs = []
    if os.path.exists(DEBUG_FILE_PATH):
        try:
            with open(DEBUG_FILE_PATH, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    logs = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            pass

    # Ensure logs is a list
    if not isinstance(logs, list):
        logs = []

    # Check if interaction_id already exists
    interaction_index = -1
    for i, interaction in enumerate(logs):
        if interaction.get("interaction_id") == interaction_id:
            interaction_index = i
            break
    
    if interaction_index >= 0:
        # Update existing interaction
        logs[interaction_index]["steps"].append(step_entry)
        # Update last modified timestamp of the interaction
        logs[interaction_index]["last_updated"] = datetime.now().isoformat()
    else:
        # Create new interaction
        new_interaction = {
            "interaction_id": interaction_id,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "steps": [step_entry]
        }
        logs.append(new_interaction)
    
    # Write back with retry logic for Windows file locking
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with open(DEBUG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(logs, f, indent=4, ensure_ascii=False)
            break # Success
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(0.5)
            else:
                print(f"Failed to write log after {max_retries} attempts: Permission denied.")
        except Exception as e:
            print(f"Failed to write log: {e}")
            break

def get_logs_by_id(interaction_id: str) -> List[Dict]:
    if not os.path.exists(DEBUG_FILE_PATH):
        return []
        
    with open(DEBUG_FILE_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)
        
    return [log for log in logs if log.get("interaction_id") == interaction_id]
