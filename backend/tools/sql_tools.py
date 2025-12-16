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
            
            # Add semantic hints for specific tables/views
            if table_name == 'swf':
                col_str += "\n    * PRIMARY P&L TABLE: Weekly financials (1934-2025)."
                col_str += "\n    * Use for: Revenue, Net Income, Costs, Expenses queries."
                col_str += "\n    * ITEMS include: 'Revenues', 'CostOfRevenue', 'OperatingExpense', 'Income Tax Expense', 'NetIncomeLoss'"
                col_str += "\n    * For 'operating expenses' → use: WHERE item LIKE '%OperatingExpense%' OR item LIKE '%pense%'"
            elif table_name == 'stock_prices':
                col_str += "\n    * STOCK DATA: Daily prices (2007-2024)."
                col_str += "\n    * Use for: Stock price, volume, trading queries."
                col_str += "\n    * For volatility: calculate std deviation of close prices, or use stock_metrics view."
            elif table_name == 'financial_targets':
                col_str += "\n    * BUDGET TABLE: Target values for variance analysis."
            elif table_name == 'profitability_metrics':
                col_str += "\n    * DERIVED VIEW: Quarterly margins (gross, operating, net)."
                col_str += "\n    * Use for: Profit margin queries, efficiency analysis."
            elif table_name == 'stock_metrics':
                col_str += "\n    * DERIVED VIEW: Monthly stock indicators."
                col_str += "\n    * Columns: yr, mo, monthly_avg_close, monthly_high, monthly_low, intraday_volatility_pct"
                col_str += "\n    * For 'volatility' queries → use intraday_volatility_pct column, AVG() for yearly."
            elif table_name == 'variance_analysis':
                col_str += "\n    * DERIVED VIEW: Budget vs Actual comparison."
                col_str += "\n    * Use for: 'Are we on target?', variance questions."
            elif table_name == 'growth_metrics':
                col_str += "\n    * DERIVED VIEW: Quarter-over-quarter growth rates."
                col_str += "\n    * Use for: Growth trends, 'is revenue growing?' queries."
            elif table_name in ['numbers', 'submissions', 'annual_metrics', 'income_statements']:
                col_str += "\n    * LEGACY: Use primary tables instead."
                
            schemas.append(f"{table_type}: {table_name}\nColumns: {col_str}")
            
        conn.close()
        return "\n\n".join(schemas)
    except Exception as e:
        return f"Error getting schemas: {e}"
