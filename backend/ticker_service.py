"""
Ticker Service - Live Financial Feed
Uses the swf (Single Weekly Financials) table for Revenue and Net Income data.
"""
import os
import sqlite3
import math


class TickerService:
    def __init__(self, db_path):
        self.db_path = db_path
        self._current_index = 0
        self._cached_timeline = []

    def _fetch_data_from_swf(self):
        """Fetch Revenue and Net Income data from swf table."""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Query swf table for Revenue and Net Income grouped by period
        query = """
        SELECT yr, qtr, item, SUM(val) as total_val
        FROM swf
        WHERE item IN ('Net Income', 'Revenue')
        GROUP BY yr, qtr, item
        ORDER BY yr DESC, qtr DESC
        LIMIT 200
        """
        try:
            rows = cursor.execute(query).fetchall()
        except Exception as e:
            print(f"Error fetching live data from swf: {e}")
            rows = []
        finally:
            conn.close()
            
        return rows

    def _process_swf_data(self, rows):
        """Convert swf rows into timeline format with Revenue and Net Income pairs."""
        period_data = {}
        
        for row in rows:
            yr = row[0]
            qtr = row[1]
            item = row[2]
            val = row[3] or 0.0
            
            period_key = f"{yr} Q{qtr}"
            
            if period_key not in period_data:
                period_data[period_key] = {"revenue": None, "net_income": None, "yr": yr, "qtr": qtr}
            
            if item == 'Revenue':
                period_data[period_key]["revenue"] = val
            elif item == 'Net Income':
                period_data[period_key]["net_income"] = val
        
        return period_data

    def _build_timeline(self, period_data):
        """Build timeline for rotating display."""
        timeline = []
        
        for period_key, metrics in period_data.items():
            rev = metrics["revenue"]
            inc = metrics["net_income"]
            
            margin = None
            is_profit = False
            
            if rev is not None and inc is not None and rev != 0:
                is_profit = inc > 0
                try:
                    margin = (inc / rev) * 100
                    if math.isinf(margin) or math.isnan(margin):
                        margin = None
                except (OverflowError, ValueError):
                    margin = None
            
            if inc is not None:
                is_profit = inc > 0
            
            timeline.append({
                "name": "Financial Overview",  # Single company view
                "period": period_key,
                "net_income": inc,
                "revenue": rev,
                "margin": round(margin, 2) if margin is not None else None,
                "is_profit": is_profit,
                "yr": metrics["yr"],
                "qtr": metrics["qtr"]
            })
        
        # Sort by year and quarter descending (newest first)
        timeline.sort(key=lambda x: (x["yr"], x["qtr"]), reverse=True)
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

    def get_batch(self, batch_size=5):
        """Get the next batch of ticker items, rotating continuously."""
        
        # Refresh cache if empty
        if not self._cached_timeline:
            rows = self._fetch_data_from_swf()
            period_data = self._process_swf_data(rows)
            self._cached_timeline = self._build_timeline(period_data)
            self._current_index = 0

        if not self._cached_timeline:
            return []

        total_points = len(self._cached_timeline)
        response_data = []
        
        for i in range(batch_size):
            idx = (self._current_index + i) % total_points
            item = self._cached_timeline[idx]
            
            response_data.append({
                "name": item["name"],
                "period": item["period"],
                "net_income": self._fmt_large_number(item['net_income']),
                "revenue": self._fmt_large_number(item['revenue']),
                "margin": f"{item['margin']}%" if item['margin'] is not None else "-",
                "is_profit": item["is_profit"],
                "status": "PROFIT" if item["is_profit"] else "LOSS"
            })
        
        # Rotate index
        self._current_index = (self._current_index + batch_size) % total_points
        
        return response_data


# Singleton instance
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "financial_data.db")
ticker_service = TickerService(DB_PATH)
