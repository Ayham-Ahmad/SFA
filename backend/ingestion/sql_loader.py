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

def get_companies_for_prompt() -> str:
    """DEPRECATED: There is no company concept anymore."""
    return ""

def resolve_company_name(user_input: str) -> dict:
    """DEPRECATED: No company resolution needed."""
    return {}

def get_company_mapping_for_prompt() -> str:
    """DEPRECATED: No company mapping needed."""
    return ""
