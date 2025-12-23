"""
Ticker Service - Live Financial Feed
====================================
Uses the swf_financials table for Revenue and Net Income data.
"""
import os
import sqlite3
import math


class TickerService:
    def __init__(self, db_path):
        self.db_path = db_path
        self._current_index = 0
        self._cached_timeline = []

    def _fetch_data_from_db(self):
        """Fetch Revenue and Net Income data from swf_financials."""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Query to get the latest year first
        year_query = "SELECT MAX(year) FROM swf_financials"
        
        # Then fetch all quarters for that year in order
        query = """
        SELECT year, quarter, revenue, net_income, net_margin
        FROM swf_financials
        WHERE year = ({})
        ORDER BY quarter ASC
        """
        try:
            latest_year = cursor.execute(year_query).fetchone()[0]
            if latest_year:
                rows = cursor.execute(query.format(year_query)).fetchall()
            else:
                rows = []
        except Exception as e:
            rows = []
        finally:
            conn.close()
            
        return rows

    def _build_timeline(self, rows):
        """Build timeline for rotating display."""
        timeline = []
        
        for row in rows:
            yr = row[0]
            qtr = row[1]
            rev = row[2]
            inc = row[3]
            margin = row[4] * 100 if row[4] is not None else None
            
            period_key = f"{yr} Q{qtr}"
            
            is_profit = False
            if inc is not None:
                is_profit = inc > 0
            
            timeline.append({
                "name": "Financial Overview",
                "period": period_key,
                "net_income": inc,
                "revenue": rev,
                "margin": round(margin, 2) if margin is not None else None,
                "is_profit": is_profit,
                "yr": yr,
                "qtr": qtr
            })
        
        return timeline

    def _fmt_large_number(self, val):
        """Format numbers with B/M/K suffixes."""
        if val is None:
            return "-"
        
        abs_val = abs(val)
        prefix = "$"
        
        if abs_val >= 1_000_000_000_000:
            formatted_num = val / 1_000_000_000_000
            suffix = "T"
        elif abs_val >= 1_000_000_000:
            formatted_num = val / 1_000_000_000
            suffix = "B"
        elif abs_val >= 1_000_000:
            formatted_num = val / 1_000_000
            suffix = "M"
        elif abs_val >= 1_000:
            formatted_num = val / 1_000
            suffix = "K"
        else:
            return f"{prefix}{val:,.2f}"
        
        s = f"{formatted_num:.1f}"
        if s.endswith(".0"):
            s = s[:-2]
        return f"{prefix}{s}{suffix}"

    def get_batch(self):
        """Get all ticker items for the current year."""
        
        # Refresh cache
        rows = self._fetch_data_from_db()
        self._cached_timeline = self._build_timeline(rows)

        if not self._cached_timeline:
            return []

        response_data = []
        for item in self._cached_timeline:
            response_data.append({
                "name": item["name"],
                "period": item["period"],
                "net_income": self._fmt_large_number(item['net_income']),
                "revenue": self._fmt_large_number(item['revenue']),
                "margin": f"{item['margin']}%" if item['margin'] is not None else "-",
                "is_profit": item["is_profit"],
                "status": "PROFIT" if item["is_profit"] else "LOSS"
            })
        
        return response_data


# Singleton instance
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")
ticker_service = TickerService(DB_PATH)
