"""
SQL Loader - Provides database metadata to help LLM generate accurate SQL queries.
Simplified for Single-Entity Advisor.
"""

# Priority columns in swf_financials
FINANCIAL_COLUMNS = [
    "revenue", "net_income", "gross_profit", "operating_expenses", 
    "operating_income", "eps_basic", "eps_diluted", "shares_outstanding",
    "gross_margin", "operating_margin", "net_margin"
]

def get_available_tags() -> list:
    """Returns available financial metrics (column names)."""
    return FINANCIAL_COLUMNS

def get_tags_for_prompt() -> str:
    """Returns a formatted string of available columns for inclusion in LLM prompt."""
    return ", ".join([f"'{col}'" for col in FINANCIAL_COLUMNS])

def get_companies_for_prompt() -> str:
    """Returns a message explaining there is only one virtual entity."""
    return "'Market Representative Entity' (Single Entity)"

def resolve_company_name(user_input: str) -> dict:
    """Always returns the single entity info."""
    return {"name": "Market Representative Entity", "cik": "N/A"}

def get_company_mapping_for_prompt() -> str:
    """Informs LLM that no company filtering is needed."""
    return "NOTE: There are no individual companies. Do NOT use CIK or Company Name filters."
