"""
Schema Utility Module
=====================
Provides dynamic schema introspection for SQL generation.
"""
import sqlite3
from typing import Dict, List
from backend.utils.paths import DB_PATH


def get_table_columns(table_name: str, db_path: str = None) -> List[str]:
    """
    Get all column names for a specific table.
    
    Args:
        table_name: Name of the table to inspect
        db_path: Optional database path (defaults to main DB_PATH)
        
    Returns:
        List of column names
    """
    if db_path is None:
        db_path = DB_PATH
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns
    except Exception as e:
        print(f"Error getting columns for {table_name}: {e}")
        return []


def get_all_tables(db_path: str = None) -> List[str]:
    """
    Get all table names from the database.
    
    Args:
        db_path: Optional database path (defaults to main DB_PATH)
        
    Returns:
        List of table names
    """
    if db_path is None:
        db_path = DB_PATH
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        print(f"Error getting tables: {e}")
        return []


def get_table_columns_with_types(table_name: str, db_path: str = None) -> List[Dict]:
    """
    Get column names with their data types.
    
    Args:
        table_name: Name of the table
        db_path: Optional database path
        
    Returns:
        List of dicts: [{"name": "col_name", "type": "INTEGER"}, ...]
    """
    if db_path is None:
        db_path = DB_PATH
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
        conn.close()
        return columns
    except Exception as e:
        print(f"Error getting column types for {table_name}: {e}")
        return []


def get_complete_schema_dict(db_path: str = None) -> Dict:
    """
    Get complete database schema as a dictionary.
    
    Returns:
        {
            "tables": ["table1", "table2"],
            "schema": {
                "table1": [{"name": "col1", "type": "INTEGER"}, ...],
                "table2": [...]
            }
        }
    """
    if db_path is None:
        db_path = DB_PATH
        
    tables = get_all_tables(db_path)
    schema = {}
    
    for table in tables:
        schema[table] = get_table_columns_with_types(table, db_path)
    
    return {
        "tables": tables,
        "schema": schema
    }


def get_columns_for_llm(db_path: str = None) -> str:
    """
    Generate a formatted string of all columns for LLM consumption.
    This is the main function to pass column information to the LLM.
    
    Returns:
        Formatted string with all tables and their columns
    """
    if db_path is None:
        db_path = DB_PATH
        
    schema_dict = get_complete_schema_dict(db_path)
    
    parts = []
    for table_name, columns in schema_dict["schema"].items():
        col_list = ", ".join([f"{c['name']} ({c['type']})" for c in columns])
        parts.append(f"TABLE: {table_name}\nCOLUMNS: {col_list}")
    
    return "\n\n".join(parts)


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
    except Exception as e:
        print(f"Schema lookup error: {e}")
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
    min_year, max_year = get_data_year_range()
    
    context = f"""AVAILABLE TABLES AND COLUMNS (from database):

{schema}

DATA RANGE: {min_year} to {max_year}

KEY COLUMNS:
- swf_financials: Financial P&L data by year/quarter

COMMON COLUMN MEANINGS:
- revenue, net_income, gross_profit: Financial metrics
- gross_margin, operating_margin, net_margin: Profitability ratios
- year, quarter: Year and quarter identifiers"""

    return context


def get_data_year_range() -> tuple:
    """
    Get the min and max year from the financial data.
    Returns (min_year, max_year) tuple.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(year), MAX(year) FROM swf_financials WHERE revenue IS NOT NULL")
        result = cursor.fetchone()
        conn.close()
        if result and result[0] and result[1]:
            return (int(result[0]), int(result[1]))
        return (2012, 2025)  # Fallback
    except Exception as e:
        print(f"Year range lookup error: {e}")
        return (2012, 2025)  # Fallback


def get_latest_year() -> int:
    """Get the most recent year with data."""
    _, max_year = get_data_year_range()
    return max_year


def get_dynamic_examples(latest_year: int = None) -> dict:
    """
    Generate dynamic example years for prompts.
    Returns dict with 'latest', 'previous', 'three_years_ago'.
    """
    if latest_year is None:
        latest_year = get_latest_year()
    
    return {
        'latest': latest_year,
        'previous': latest_year - 1,
        'three_years_ago': latest_year - 3,
    }


if __name__ == "__main__":
    print("=== Schema for Prompt ===")
    print(get_schema_for_prompt())
    print("\n=== Full Context ===")
    print(get_full_schema_context())
