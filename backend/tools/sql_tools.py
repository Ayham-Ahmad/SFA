import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
import os

DB_PATH = "data/db/financial_data.db"

def format_financial_value(val):
    """Format large numbers to readable format like $219.66B"""
    try:
        val = float(val)
        if abs(val) >= 1e12:
            return f"${val/1e12:.2f}T"
        elif abs(val) >= 1e9:
            return f"${val/1e9:.2f}B"
        elif abs(val) >= 1e6:
            return f"${val/1e6:.2f}M"
        elif abs(val) >= 1e3:
            return f"${val/1e3:.2f}K"
        else:
            return f"${val:,.2f}"
    except:
        return str(val)

def format_date(ddate):
    """Format YYYYMMDD integer to YYYY-MM-DD string"""
    try:
        ddate_str = str(int(ddate))
        if len(ddate_str) == 8:
            return f"{ddate_str[:4]}-{ddate_str[4:6]}-{ddate_str[6:]}"
        return ddate_str
    except:
        return str(ddate)

def execute_sql_query(query: str) -> str:
    """
    Execute a read-only SQL query on the financial database.
    Returns the result as a markdown table string or error message.
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
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        schemas = []
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        
        for table in tables:
            table_name = table[0]
            columns = cursor.execute(f"PRAGMA table_info({table_name});").fetchall()
            col_str = ", ".join([f"{col[1]} ({col[2]})" for col in columns])
            
            # Add semantic hints for specific tables
            if table_name == 'numbers':
                col_str += "\n    * HINTS: 'ddate' is integer YYYYMMDD. 'uom' is Unit. 'tag' is the Concept Name.\n    * COMMON TAGS (Use EXACTLY): 'NetIncomeLoss', 'Revenues', 'GrossProfit', 'OperatingIncomeLoss', 'Assets', 'Liabilities', 'StockholdersEquity', 'CashAndCashEquivalentsAtCarryingValue', 'EarningsPerShareBasic', 'ProfitLoss'."
            elif table_name == 'submissions':
                col_str += "\n    * HINTS: 'sic' is Industry Code. 'countryba' is Country. 'name' is Company Name (e.g. APPLE INC., MICROSOFT CORP)."
            elif table_name == 'annual_metrics':
                col_str += "\n    * RECOMMENDED TABLE FOR ANNUAL DATA! Pre-aggregated by company/year."
                col_str += "\n    * HINTS: 'company_name' is SEC-official name. 'fiscal_year' is integer YYYY. 'value' is MAX value for that year."
                col_str += "\n    * USE THIS TABLE for simple annual queries instead of complex GROUP BY on numbers table."
                
            schemas.append(f"Table: {table_name}\nColumns: {col_str}")
            
        conn.close()
        return "\n\n".join(schemas)
    except Exception as e:
        return f"Error getting schemas: {e}"
