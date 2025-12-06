import sqlite3
import pandas as pd
from typing import List, Dict, Any, Optional
import os

DB_PATH = "data/db/financial_data.db"

def execute_sql_query(query: str) -> str:
    """
    Execute a read-only SQL query on the financial database.
    Returns the result as a markdown table string or error message.
    """
    # Security check: only allow SELECT statements
    if not query.strip().lower().startswith("select"):
        return "Error: Only SELECT statements are allowed."
    
    if "drop" in query.lower() or "delete" in query.lower() or "update" in query.lower() or "insert" in query.lower():
        return "Error: Unsafe SQL keywords detected."

    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return "No results found."
        
        # Safety: Limit rows to prevent massive context
        if len(df) > 50:
            df = df.head(50)
            return df.to_markdown(index=False) + "\n\n(Result truncated to first 50 rows to save tokens)"
            
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
                col_str += "\n    * HINTS: 'ddate' is integer YYYYMMDD (e.g. 20231231). 'uom' is Unit (USD, VND, etc). ALWAYS SELECT 'uom' with 'value'. 'tag' is the financial concept (e.g., NetIncomeLoss, Revenues)."
            elif table_name == 'submissions':
                col_str += "\n    * HINTS: 'sic' is Industry Code. 'countryba' is Country. 'name' is Company Name (e.g. APPLE INC., MICROSOFT CORP)."
                
            schemas.append(f"Table: {table_name}\nColumns: {col_str}")
            
        conn.close()
        return "\n\n".join(schemas)
    except Exception as e:
        return f"Error getting schemas: {e}"
