"""
SQL Tools
=========
Database query execution and schema utilities.
"""
import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
from backend.utils.paths import DB_PATH
from backend.utils.formatters import format_financial_value, format_date


def execute_sql_query(query: str) -> str:
    """
    Execute a read-only SQL query on the financial database.
    
    Args:
        query: SQL SELECT statement
        
    Returns:
        Result as a markdown table string or error message.
    """
    normalized = query.strip().lower()
    
    # Security check: allow SELECT and CTEs (WITH ... SELECT)
    if not (normalized.startswith("select") or normalized.startswith("with")):
        return "Error: Only SELECT statements are allowed."
    
    # Block dangerous operations
    unsafe_keywords = ["drop", "delete", "update", "insert", "alter", "create", "truncate"]
    for keyword in unsafe_keywords:
        if keyword in normalized:
            return f"Error: Unsafe SQL keyword '{keyword}' detected."

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return "No results found."
        
        # Format financial values for readability
        if 'value' in df.columns:
            df['value'] = df['value'].apply(format_financial_value)
        if 'value_usd' in df.columns:
            df['value_usd'] = df['value_usd'].apply(format_financial_value)
        if 'val' in df.columns:
            df['val'] = df['val'].apply(format_financial_value)
        if 'ddate' in df.columns:
            df['ddate'] = df['ddate'].apply(format_date)
        
        # Safety: Limit rows to prevent massive context
        if len(df) > 200:
            df = df.head(200)
            return df.to_markdown(index=False) + "\n\n(Result truncated to first 200 rows to save tokens)"
            
        return df.to_markdown(index=False)
    except Exception as e:
        return f"SQL Error: {e}"


def get_table_schemas() -> str:
    """
    Get the schema of all tables in the database to help the LLM write queries.
    
    Returns:
        Formatted string with table/view names and their columns with hints.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        schemas = []
        
        # Get tables AND views
        tables = cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view');").fetchall()
        
        for table in tables:
            table_name = table[0]
            table_type = table[1].upper()
            columns = cursor.execute(f"PRAGMA table_info({table_name});").fetchall()
            col_str = ", ".join([f"{col[1]} ({col[2]})" for col in columns])
            
            # Add semantic hints for swf_financials (primary table)
            if table_name == 'swf_financials':
                # Dynamically get year range from data
                try:
                    cursor.execute("SELECT MIN(year), MAX(year) FROM swf_financials WHERE revenue IS NOT NULL")
                    min_yr, max_yr = cursor.fetchone()
                    if min_yr and max_yr:
                        col_str += f"\n    * PRIMARY FINANCIAL TABLE: Data from {min_yr} to {max_yr}."
                    else:
                        col_str += "\n    * PRIMARY FINANCIAL TABLE: Financial P&L data."
                except Exception:
                    col_str += "\n    * PRIMARY FINANCIAL TABLE: Financial P&L data."
                col_str += "\n    * Use for: Revenue, Net Income, Gross Profit, Operating Expenses, Margins."
                
            schemas.append(f"{table_type}: {table_name}\nColumns: {col_str}")
            
        conn.close()
        return "\n\n".join(schemas)
    except Exception as e:
        return f"Error getting schemas: {e}"
