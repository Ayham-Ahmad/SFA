"""
Analytics Metrics Module
Fetches key financial metrics for the dashboard using swf and stock_prices tables.
"""
import sqlite3
import pandas as pd
import os
import math
from typing import Dict, Any

# Use absolute path for robustness
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")


def get_key_metrics() -> Dict[str, Any]:
    """
    Fetch key financial metrics for the dashboard.
    Uses swf table for revenue and net income totals.
    """
    try:
        if not os.path.exists(DB_PATH):
            return {"total_revenue": 0, "total_net_income": 0, "latest_year": None}

        conn = sqlite3.connect(DB_PATH)
        
        # Get the latest year's total revenue from swf
        revenue_query = """
        SELECT yr, SUM(val) as total_rev 
        FROM swf 
        WHERE item = 'Revenue' 
        GROUP BY yr 
        ORDER BY yr DESC 
        LIMIT 1
        """
        rev_result = conn.execute(revenue_query).fetchone()
        latest_year = rev_result[0] if rev_result else None
        total_revenue = rev_result[1] if rev_result else 0
        
        # Get the latest year's total net income from swf
        income_query = """
        SELECT SUM(val) 
        FROM swf 
        WHERE item = 'Net Income' AND yr = ?
        """
        income_result = conn.execute(income_query, (latest_year,)).fetchone() if latest_year else None
        total_net_income = income_result[0] if income_result and income_result[0] else 0
        
        conn.close()
        
        return {
            "total_revenue": total_revenue,
            "total_net_income": total_net_income,
            "latest_year": latest_year
        }
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        return {"total_revenue": 0, "total_net_income": 0, "latest_year": None}


def get_revenue_trend() -> Dict[str, Any]:
    """
    Get quarterly Revenue trend data for plotting.
    Uses swf table grouped by year and quarter.
    """
    try:
        if not os.path.exists(DB_PATH):
            return {"dates": [], "values": []}
            
        conn = sqlite3.connect(DB_PATH)
        
        query = """
        SELECT yr, qtr, SUM(val) as total_rev 
        FROM swf 
        WHERE item = 'Revenue'
        GROUP BY yr, qtr
        ORDER BY yr, qtr
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"dates": [], "values": []}

        # Create period labels like "2024 Q1"
        dates = [f"{int(row['yr'])} Q{int(row['qtr'])}" for _, row in df.iterrows()]
        
        # Clean values
        values = [0.0 if pd.isna(x) or math.isinf(x) else float(x) for x in df['total_rev'].tolist()]
        
        return {
            "dates": dates,
            "values": values
        }
    except Exception as e:
        print(f"Error fetching revenue trend: {e}")
        return {"dates": [], "values": []}


def get_income_trend() -> Dict[str, Any]:
    """
    Get quarterly Net Income trend data for plotting.
    Uses swf table grouped by year and quarter.
    """
    try:
        if not os.path.exists(DB_PATH):
            return {"dates": [], "values": []}
            
        conn = sqlite3.connect(DB_PATH)
        
        query = """
        SELECT yr, qtr, SUM(val) as total_income
        FROM swf 
        WHERE item = 'Net Income'
        GROUP BY yr, qtr
        ORDER BY yr, qtr
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"dates": [], "values": []}

        # Create period labels like "2024 Q1"
        dates = [f"{int(row['yr'])} Q{int(row['qtr'])}" for _, row in df.iterrows()]
        
        # Clean values
        values = [0.0 if pd.isna(x) or math.isinf(x) else float(x) for x in df['total_income'].tolist()]
            
        return {
            "dates": dates,
            "values": values
        }
    except Exception as e:
        print(f"Error fetching income trend: {e}")
        return {"dates": [], "values": []}
