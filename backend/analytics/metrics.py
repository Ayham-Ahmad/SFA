import sqlite3
import pandas as pd
import os
from typing import Dict, Any

# Use absolute path for robustness
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")

def get_key_metrics() -> Dict[str, Any]:
    """
    Fetch key financial metrics for the dashboard.
    """
    try:
        if not os.path.exists(DB_PATH):
             return {"total_assets": 0, "total_revenue": 0, "company_count": 0}

        conn = sqlite3.connect(DB_PATH)
        
        # 1. Total Assets (Example: Sum of latest AssetsCurrent for all companies)
        assets_query = "SELECT SUM(value) FROM numbers WHERE tag = 'AssetsCurrent'"
        total_assets = conn.execute(assets_query).fetchone()[0] or 0
        
        # 2. Total Revenue (Example: Sum of Revenues)
        revenue_query = "SELECT SUM(value) FROM numbers WHERE tag = 'Revenues'"
        total_revenue = conn.execute(revenue_query).fetchone()[0] or 0
        
        # 3. Company Count
        company_query = "SELECT COUNT(DISTINCT name) FROM submissions"
        company_count = conn.execute(company_query).fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_assets": total_assets,
            "total_revenue": total_revenue,
            "company_count": company_count
        }
    except Exception as e:
        print(f"Error fetching metrics: {e}")
        return {"total_assets": 0, "total_revenue": 0, "company_count": 0}

def get_revenue_trend() -> Dict[str, Any]:
    """
    Get aggregated Total Revenue trend data for plotting.
    Groups by date to show market-wide performance.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        # Aggregate by date to resolve specific company noise
        query = """
        SELECT ddate, SUM(value) as total_rev 
        FROM numbers 
        WHERE tag = 'Revenues' 
        GROUP BY ddate
        ORDER BY ddate
        LIMIT 100
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"dates": [], "values": []}

        import math
        values = [0.0 if pd.isna(x) or math.isinf(x) else x for x in df['total_rev'].tolist()]
        
        # Convert YYYYMMDD integer/string to YYYY-MM-DD string
        dates = pd.to_datetime(df['ddate'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d').fillna('').tolist()

        return {
            "dates": dates,
            "values": values
        }
    except Exception as e:
        print(f"Error fetching revenue trend: {e}")
        return {"dates": [], "values": []}

def get_income_trend() -> Dict[str, Any]:
    """
    Get aggregated Net Income trend data for plotting.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        # Aggregate by date
        query = """
        SELECT ddate, SUM(value) as total_income
        FROM numbers 
        WHERE tag = 'NetIncomeLoss'
        GROUP BY ddate
        ORDER BY ddate
        LIMIT 100
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return {"dates": [], "values": []}

        import math
        values = [0.0 if pd.isna(x) or math.isinf(x) else x for x in df['total_income'].tolist()]
        
        # Convert YYYYMMDD integer/string to YYYY-MM-DD string
        dates = pd.to_datetime(df['ddate'], format='%Y%m%d', errors='coerce').dt.strftime('%Y-%m-%d').fillna('').tolist()
            
        return {
            "dates": dates,
            "values": values
        }
    except Exception as e:
        print(f"Error fetching income trend: {e}")
        return {"dates": [], "values": []}
