"""
Centralized Groq LLM Client
===========================
Singleton pattern for Groq API client to avoid multiple initializations.
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
    "default": "llama-3.3-70b-versatile",
    "fast": "llama-3.1-8b-instant",
    "worker": "qwen/qwen3-32b",
    "auditor": "meta-llama/llama-4-scout-17b-16e-instruct",
}

def get_model(task: str = "default") -> str:
    """Get model name for a specific task type."""
    return MODELS.get(task, MODELS["default"])
