"""
Query Progress Tracking
=======================
Centralized progress tracking for chat queries.
This is a separate module to avoid circular imports between chat.py and routing.py.
"""

# Global state for tracking active queries
active_queries = {}     # Maps query_id -> asyncio Task
query_progress = {}     # Maps query_id -> Status message


def set_query_progress(query_id: str, agent: str, step: str = ""):
    """Updates the status message for the frontend loading bar."""
    if query_id:
        query_progress[query_id] = {"agent": agent, "step": step}


def clear_query_progress(query_id: str):
    """Remove progress tracking for completed query."""
    query_progress.pop(query_id, None)


def get_query_progress(query_id: str) -> dict:
    """Get current progress for a query."""
    return query_progress.get(query_id, {"agent": "initializing", "step": "⏳ Starting..."})
