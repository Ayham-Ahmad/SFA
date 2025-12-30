"""
SQL Tools
=========
Database query execution and schema utilities.
Requires user-specific database connection - no default fallback.
"""
import pandas as pd
from typing import List, Dict, Any, Optional
from backend.utils.formatters import format_financial_value, format_date


def execute_sql_query(query: str, user=None) -> str:
    """
    Execute a read-only SQL query on the user's connected database.
    
    Args:
        query: SQL SELECT statement
        user: User model instance for tenant-specific queries (REQUIRED)
        
    Returns:
        Result as a markdown table string or error message.
    """
    # Clean up query - strip whitespace and backticks (LLM sometimes wraps in backticks)
    query = query.strip().strip('`').strip()
    normalized = query.lower()
    
    # Security check: allow SELECT and CTEs (WITH ... SELECT)
    if not (normalized.startswith("select") or normalized.startswith("with")):
        return "Error: Only SELECT statements are allowed."
    
    # Block dangerous operations
    unsafe_keywords = ["drop", "delete", "update", "insert", "alter", "create", "truncate"]
    for keyword in unsafe_keywords:
        if keyword in normalized:
            return f"Error: Unsafe SQL keyword '{keyword}' detected."

    try:
        # REQUIRE user-specific database - no default fallback
        if not user or not user.db_is_connected:
            return "Error: No database connected. Please connect a database in Settings first."
        
        from backend.services.tenant_manager import MultiTenantDBManager
        result = MultiTenantDBManager.execute_query_for_user(user, query)
        
        if not result.get("success"):
            return f"Error: {result.get('error', 'Query failed')}"
        
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        
        if not rows:
            return "No results found."
        
        df = pd.DataFrame(rows, columns=columns)
        
        if df.empty:
            return "No results found."
        
        # Format financial values for readability - apply to ALL numeric columns
        for col in df.columns:
            if df[col].dtype in ['float64', 'int64']:
                # Check if values are large enough to need formatting
                max_val = df[col].abs().max()
                if max_val > 10000:  # Format if values > 10,000
                    df[col] = df[col].apply(format_financial_value)
            elif col.lower() == 'ddate':
                df[col] = df[col].apply(format_date)
        
        # Safety: Limit rows to prevent massive context
        if len(df) > 200:
            df = df.head(200)
            return df.to_markdown(index=False) + "\n\n(Result truncated to first 200 rows to save tokens)"
            
        return df.to_markdown(index=False)
    except Exception as e:
        return f"SQL Error: {e}"


def get_table_schemas(user=None) -> str:
    """
    Get the schema of all tables in the user's connected database.
    
    Args:
        user: User model instance for tenant-specific schema (REQUIRED)
    
    Returns:
        Formatted string with table/view names and their columns.
    """
    try:
        # REQUIRE user-specific database - no default fallback
        if not user or not user.db_is_connected:
            return "No database connected. Please connect a database in Settings."
        
        from backend.services.tenant_manager import MultiTenantDBManager
        from backend.core.logger import log_system_debug, log_system_error
        
        schema_result = MultiTenantDBManager.get_schema_for_user(user)
        
        log_system_debug(f"[sql_tools] get_schema_for_user result: success={schema_result.get('success')}, has_schema_for_llm={bool(schema_result.get('schema_for_llm'))}, tables_count={len(schema_result.get('tables', {}))}")
        
        if schema_result.get("success") and schema_result.get("schema_for_llm"):
            return schema_result["schema_for_llm"]
        
        # Fallback: build schema from tables dict
        tables = schema_result.get("tables", {})
        schemas = []
        for table_name, table_info in tables.items():
            # Handle both dict format and list format
            if isinstance(table_info, dict):
                columns = table_info.get("columns", [])
            else:
                columns = table_info if isinstance(table_info, list) else []
            col_str = ", ".join([f"{col['name']} ({col['type']})" for col in columns if isinstance(col, dict)])
            schemas.append(f"TABLE: {table_name}\nColumns: {col_str}")
        return "\n\n".join(schemas) if schemas else "No tables found in connected database."
        
    except Exception as e:
        return f"Error getting schemas: {e}"
