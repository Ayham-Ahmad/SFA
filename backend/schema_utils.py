"""
Schema Utility Module
=====================

Provides dynamic schema introspection for SQL generation.
Fetches actual column names from the database to ensure LLM
has accurate information for query generation.
"""

import sqlite3
import os
from typing import Dict, List

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db', 'financial_data.db')


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
    Dynamically fetches columns from the actual database tables.
    
    Returns:
        Formatted string with table names and their columns
    """
    tables = ['swf_financials', 'market_daily_data']
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
    
    Returns:
        Detailed schema string for LLM context
    """
    schema = get_schema_for_prompt()
    
    context = f"""AVAILABLE TABLES AND COLUMNS (from database):

{schema}

KEY COLUMNS:
- swf_financials: Financial P&L data by year/quarter
- market_daily_data: Daily stock prices and volatility

COMMON COLUMN MEANINGS:
- open_price, high_price, low_price, close_price: Daily stock prices
- trade_volume: Number of shares traded
- rolling_volatility: Price volatility measure
- daily_return_pct: Daily percentage return
- revenue, net_income, gross_profit: Financial metrics
- gross_margin, operating_margin, net_margin: Profitability ratios

JOIN RULE (only if combining financial + market data):
swf_financials.year = market_daily_data.year
AND swf_financials.quarter = market_daily_data.fiscal_quarter
When joining, ALWAYS aggregate market data (AVG, MAX, MIN)."""

    return context


if __name__ == "__main__":
    # Test the schema fetching
    print("=== Schema for Prompt ===")
    print(get_schema_for_prompt())
    print("\n=== Full Context ===")
    print(get_full_schema_context())
