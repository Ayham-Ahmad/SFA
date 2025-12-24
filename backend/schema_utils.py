"""
Schema Utility Module
=====================
Provides dynamic schema introspection for SQL generation.
"""
import sqlite3
from typing import Dict, List
from backend.utils.paths import DB_PATH


def get_table_columns(table_name: str) -> List[str]:
    """
    Get all column names for a specific table.
    
    Args:
        table_name: Name of the table to inspect
        
    Returns:
        List of column names
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns
    except Exception as e:
        print(f"Error getting columns for {table_name}: {e}")
        return []


def get_schema_for_prompt() -> str:
    """
    Generate a formatted schema string for the SQL generation prompt.
    Dynamically discovers all tables in the database.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception:
        tables = ['swf_financials']  # Fallback
    
    schema_parts = []
    for table in tables:
        columns = get_table_columns(table)
        if columns:
            column_list = '\n'.join([f"  - {col}" for col in columns])
            schema_parts.append(f"{table}:\n{column_list}")
    
    return '\n\n'.join(schema_parts)


def get_full_schema_context() -> str:
    """
    Generate complete schema context for LLM including column types and descriptions.
    """
    schema = get_schema_for_prompt()
    
    context = f"""AVAILABLE TABLES AND COLUMNS (from database):

{schema}

KEY COLUMNS:
- swf_financials: Financial P&L data by year/quarter

COMMON COLUMN MEANINGS:
- revenue, net_income, gross_profit: Financial metrics
- gross_margin, operating_margin, net_margin: Profitability ratios
- yr, qtr: Year and quarter identifiers"""

    return context


if __name__ == "__main__":
    print("=== Schema for Prompt ===")
    print(get_schema_for_prompt())
    print("\n=== Full Context ===")
    print(get_full_schema_context())
