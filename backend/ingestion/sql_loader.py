"""
SQL Loader - DEPRECATED
=======================
This module is kept for backward compatibility with tests.
Schema information is now dynamically obtained from user's connected database.
"""

# These constants are kept for test compatibility only
FINANCIAL_COLUMNS = []

def get_available_tags() -> list:
    """DEPRECATED: Returns empty list. Schema is now dynamic per user."""
    return []

def get_tags_for_prompt() -> str:
    """DEPRECATED: Returns empty string. Schema is now dynamic per user."""
    return ""
