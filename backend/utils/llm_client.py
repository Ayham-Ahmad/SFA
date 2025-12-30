"""
Centralized Groq LLM Client
===========================
Singleton pattern for Groq API client to avoid multiple initializations.
Includes API call counter for monitoring usage.
"""
from groq import Groq
import os
from dotenv import load_dotenv

# Load environment variables once
load_dotenv()

# Singleton Groq client instance
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Available models for different tasks
MODELS = {
    "default": "llama-3.3-70b-versatile",  # Better reasoning
    "fast": "llama-3.1-8b-instant",
}

# --- API Call Counter ---
_api_call_count = 0
_api_call_details = []

def get_model(task: str = "default") -> str:
    """Get model name for a specific task type."""
    return MODELS.get(task, MODELS["default"])

def increment_api_counter(model: str = None, tokens_used: int = 0):
    """Increment the API call counter and log details."""
    global _api_call_count, _api_call_details
    _api_call_count += 1
    _api_call_details.append({
        "call_num": _api_call_count,
        "model": model or "unknown",
        "tokens": tokens_used
    })
    print(f"📊 API Call #{_api_call_count} (Model: {model}, Tokens: {tokens_used})")

def get_api_call_count() -> int:
    """Get the current API call count."""
    global _api_call_count
    return _api_call_count

def get_api_call_details() -> list:
    """Get details of all API calls."""
    global _api_call_details
    return _api_call_details

def reset_api_counter():
    """Reset the API call counter (call at start of each evaluation)."""
    global _api_call_count, _api_call_details
    _api_call_count = 0
    _api_call_details = []
    print("📊 API Counter reset to 0")

def print_api_summary():
    """Print a summary of API usage."""
    global _api_call_count, _api_call_details
    total_tokens = sum(d.get("tokens", 0) for d in _api_call_details)
    print(f"\n📊 API USAGE SUMMARY:")
    print(f"   Total Calls: {_api_call_count}")
    print(f"   Total Tokens: {total_tokens}")
    for d in _api_call_details:
        print(f"   - Call {d['call_num']}: {d['model']} ({d['tokens']} tokens)")

