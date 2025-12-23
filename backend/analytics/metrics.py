"""
Analytics Metrics Module
========================
Fetches key financial metrics for the dashboard using swf_financials table.
"""
import sqlite3
import pandas as pd
from typing import Dict, Any
from backend.utils.paths import DB_PATH
from backend.utils.formatters import format_large_number
import os


def get_key_metrics() -> Dict[str, Any]:
    """
    Fetch key financial metrics for the dashboard.
    Uses swf_financials table for revenue and net income totals.
    """
    try:
        if not os.path.exists(DB_PATH):
            return {"total_revenue": 0, "total_net_income": 0, "latest_year": None}

        conn = sqlite3.connect(DB_PATH)
        
        # Get the latest year's total revenue from swf_financials
        latest_year_query = "SELECT MAX(year) FROM swf_financials"
        latest_year = conn.execute(latest_year_query).fetchone()[0]
        
        if not latest_year:
            conn.close()
            return {"total_revenue": 0, "total_net_income": 0, "latest_year": None}
            
        metrics_query = """
        SELECT SUM(revenue), SUM(net_income)
        FROM swf_financials
        WHERE year = ?
        """
        result = conn.execute(metrics_query, (latest_year,)).fetchone()
        total_revenue = result[0] if result and result[0] else 0
        total_net_income = result[1] if result and result[1] else 0
        
        conn.close()
        
        return {
            "total_revenue": total_revenue,
            "total_net_income": total_net_income,
            "latest_year": latest_year
        }
    except Exception as e:
        return {"total_revenue": 0, "total_net_income": 0, "latest_year": None}


def get_revenue_trend() -> Dict[str, Any]:
    """
    Get quarterly Revenue trend data for plotting.
    Uses swf_financials table.
    """
    try:
        if not os.path.exists(DB_PATH):
            return {"dates": [], "values": []}
            
        conn = sqlite3.connect(DB_PATH)
        
        query = """
        SELECT year, quarter, revenue
        FROM swf_financials
        ORDER BY year, quarter
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"dates": [], "values": []}

        # Create period labels like "2024 Q1"
        dates = [f"{int(row['year'])} Q{int(row['quarter'])}" for _, row in df.iterrows()]
        values = [float(x) if x is not None else 0.0 for x in df['revenue'].tolist()]
        
        return {
            "dates": dates,
            "values": values
        }
    except Exception as e:
        return {"dates": [], "values": []}


def get_income_trend() -> Dict[str, Any]:
    """
    Get quarterly Net Income trend data for plotting.
    Uses swf_financials table.
    """
    try:
        if not os.path.exists(DB_PATH):
            return {"dates": [], "values": []}
            
        conn = sqlite3.connect(DB_PATH)
        
        query = """
        SELECT year, quarter, net_income
        FROM swf_financials
        ORDER BY year, quarter
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"dates": [], "values": []}

        # Create period labels like "2024 Q1"
        dates = [f"{int(row['year'])} Q{int(row['quarter'])}" for _, row in df.iterrows()]
        values = [float(x) if x is not None else 0.0 for x in df['net_income'].tolist()]
            
        return {
            "dates": dates,
            "values": values
        }
    except Exception as e:
        return {"dates": [], "values": []}
