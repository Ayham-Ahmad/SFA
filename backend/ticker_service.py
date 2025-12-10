import os
import sqlite3
import math

class TickerService:
    def __init__(self, db_path):
        self.db_path = db_path
        self._current_index = 0
        self._cached_timeline = []
        self._last_company_filter = None

    def _fetch_raw_data(self):
        """Fetch raw NIL and Revenue data from SQLite."""
        if not os.path.exists(self.db_path):
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
        SELECT s.name, n.ddate, n.tag, n.value, n.uom
        FROM submissions s
        JOIN numbers n ON s.adsh = n.adsh
        WHERE n.tag IN ('NetIncomeLoss', 'Revenues')
        ORDER BY n.ddate ASC
        """
        try:
            rows = cursor.execute(query).fetchall()
        except Exception as e:
            print(f"Error fetching live data: {e}")
            rows = []
        finally:
            conn.close()
            
        return rows

    def _process_data(self, rows):
        """Group raw rows into company timeline objects."""
        company_map = {}
        
        for row in rows:
            name = row[0]
            date = str(row[1])
            tag = row[2]
            try:
                val = float(row[3])
            except (ValueError, TypeError):
                val = 0.0
            
            uom = row[4]
            if not uom: uom = "USD"
            
            if name not in company_map:
                company_map[name] = {}
            if date not in company_map[name]:
                company_map[name][date] = {"income": None, "revenue": None, "currency": uom}
                
            if tag == 'NetIncomeLoss':
                company_map[name][date]["income"] = val
            elif tag == 'Revenues':
                company_map[name][date]["revenue"] = val
                company_map[name][date]["currency"] = uom
        
        return company_map

    def _build_timeline(self, company_map):
        """Flatten grouped data into a sorted timeline."""
        timeline = []
        for name, dates_dict in company_map.items():
            for d, metrics in dates_dict.items():
                inc = metrics["income"]
                rev = metrics["revenue"]
                curr = metrics.get("currency", "USD")
                
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
                    "name": name,
                    "period": d,
                    "net_income": inc,
                    "revenue": rev,
                    "margin": round(margin, 2) if margin is not None else None,
                    "is_profit": is_profit,
                    "currency": curr
                })
        
        # Sort chronologically
        timeline.sort(key=lambda x: str(x["period"]))
        return timeline

    def _fmt_large_number(self, val):
        """Format numbers with B/M/K suffixes."""
        if val is None: return "-"
        
        abs_val = abs(val)
        suffix = ""
        formatted_num = val
        
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
            return f"{val:,.2f}"
            
        s = f"{formatted_num:.1f}"
        if s.endswith(".0"):
            s = s[:-2]
        return f"{s}{suffix}"

    def get_batch(self, companies_filter=None, batch_size=5):
        """Get the next batch of ticker items, rotating continuously."""
        
        # Simple caching/refresh strategy: Re-fetch if filter changes or first run
        # In a real app, you might want a time-based TTL or dedicated background worker
        if not self._cached_timeline or self._last_company_filter != companies_filter:
            rows = self._fetch_raw_data()
            company_map = self._process_data(rows)
            timeline = self._build_timeline(company_map)
            
            # Filter
            if companies_filter:
                search_terms = [c.lower() for c in companies_filter if c.strip()]
                if search_terms:
                    timeline = [t for t in timeline if any(term in t["name"].lower() for term in search_terms)]
            
            self._cached_timeline = timeline
            self._last_company_filter = companies_filter
            self._current_index = 0 # Reset index on filter change

        if not self._cached_timeline:
            return []

        total_points = len(self._cached_timeline)
        response_data = []
        
        for i in range(batch_size):
            idx = (self._current_index + i) % total_points
            item = self._cached_timeline[idx]
            
            currency_badge = f" ({item['currency']})" if item['currency'] != "USD" else ""

            response_data.append({
                "name": item["name"],
                "period": item["period"],
                "net_income": self._fmt_large_number(item['net_income']) + currency_badge,
                "revenue": self._fmt_large_number(item['revenue']) + currency_badge,
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
