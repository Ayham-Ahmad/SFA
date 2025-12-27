"""
Ticker Service - Live Financial Feed
====================================
Dynamic service that fetches ticker data based on user configuration.
"""
from backend.tenant_manager import MultiTenantDBManager
from backend.utils.formatters import format_large_number
from backend.sfa_logger import log_system_debug, log_system_error
import pandas as pd

class TickerService:
    def get_batch(self, user, config):
        """
        Get ticker items based on user configuration.
        """
        if not user.db_is_connected or not config:
            return []

        # 1. Identify columns to fetch logic
        # Filter out empty metrics to find primary table
        metrics = [
            config.traffic_light.metric1_column,
            config.traffic_light.metric2_column, 
            config.traffic_light.metric3_column
        ]
        active_metrics = [m for m in metrics if m]
        
        if not active_metrics:
            return []
            
        # 2. Determine primary table
        try:
            primary_table = active_metrics[0].split('.')[0]
        except IndexError:
            return []

        # 3. Build Query - FETCH ALL columns to support any expression
        # ALWAYS sort by rowid DESC to get the physically last inserted row.
        query = f'SELECT * FROM "{primary_table}" ORDER BY rowid DESC LIMIT 1'
        
        # Execute
        result = MultiTenantDBManager.execute_query_for_user(user, query)
        
        if not result.get("success") or not result.get("rows") or not result.get("columns"):
            return []
            
        rows = result["rows"]
        columns = result["columns"]
        
        # 4. Process Rows into Timeline
        timeline = []
        
        expression = config.traffic_light.expression
        green_thresh = config.traffic_light.green_threshold
        red_thresh = config.traffic_light.red_threshold
        
        # Helper to safely get metric value from row dict
        def get_val(row_dict, full_col_name):
            if not full_col_name: return None
            # metrics are like "table.col" or just "col" if user manually edited
            # But DB columns are just "col"
            parts = full_col_name.split('.')
            col_key = parts[1] if len(parts) > 1 else parts[0]
            return row_dict.get(col_key)

        for row in rows:
            # Map row values to column names
            row_dict = dict(zip(columns, row))
            
            # Prepare context for evaluation - use ALL available columns
            eval_context = {k: (v if v is not None else 0) for k, v in row_dict.items()}
                
            # Evaluate Status
            is_profit = None # Default to Neutral/Yellow if unsure
            status_text = "NORMAL"
            
            # Calc debug info
            calc_debug = {}
            
            try:
                if expression:
                    # Evaluate expression
                    # eval_context has all columns, so 'cost_of_revenue' will work if in table
                    val = eval(expression, {"__builtins__": None}, eval_context)
                    
                    # Identify used variables for tooltip (heuristic)
                    used_vars = {k: v for k, v in eval_context.items() if k in expression}
                    calc_debug = {
                        "result": val,
                        "green": green_thresh,
                        "red": red_thresh,
                        "vars": used_vars
                    }
                    
                    if val >= green_thresh:
                        is_profit = True
                        status_text = "GOOD"
                    elif val < red_thresh:
                        is_profit = False
                        status_text = "CRITICAL"
                    else:
                         is_profit = None # Neutral state
                         status_text = "NEUTRAL"
                else:
                    # No expression configured
                    status_text = "NO EXPR"
            except Exception as e:
                # Capture error for debugging but don't crash
                log_system_error(f"Traffic Light Eval Error: {e}")
                is_profit = "error" 
                status_text = "ERROR"
                calc_debug = {"error": str(e)}

            # Get metric values for display
            m1_val = get_val(row_dict, config.traffic_light.metric1_column)
            m2_val = get_val(row_dict, config.traffic_light.metric2_column)
            m3_val = get_val(row_dict, config.traffic_light.metric3_column)
            
            # Subtitle - combine primary and secondary if both exist
            sub_col = config.ticker_title_column
            sub_secondary_col = config.ticker_title_secondary_column
            subtitle_val = None
            
            if sub_col:
                parts = sub_col.split('.')
                sub_key = parts[1] if len(parts) > 1 else parts[0]
                primary_val = row_dict.get(sub_key)
                
                # Check for secondary column
                if sub_secondary_col and primary_val is not None:
                    sec_parts = sub_secondary_col.split('.')
                    sec_key = sec_parts[1] if len(sec_parts) > 1 else sec_parts[0]
                    secondary_val = row_dict.get(sec_key)
                    
                    if secondary_val is not None:
                        subtitle_val = f"{primary_val} {secondary_val}"
                    else:
                        subtitle_val = primary_val
                else:
                    subtitle_val = primary_val

            # Format item
            from backend.utils.formatters import format_value
            
            timeline.append({
                "name": "Financial Overview",
                "subtitle_value": format_value(subtitle_val, config.ticker_title_format) if subtitle_val else "",
                "metric1": format_value(m1_val, config.traffic_light.metric1_format),
                "metric1_label": self._get_label_from_col(config.traffic_light.metric1_column),
                "metric2": format_value(m2_val, config.traffic_light.metric2_format),
                "metric2_label": self._get_label_from_col(config.traffic_light.metric2_column),
                "metric3": format_value(m3_val, config.traffic_light.metric3_format),
                "metric3_label": self._get_label_from_col(config.traffic_light.metric3_column),
                "is_profit": is_profit,
                "expression": expression if expression else "No Expression",
                "calc_details": calc_debug,
                # Force status to string just in case
                "status": str(status_text)
            })
            
        return timeline


    def _get_label_from_col(self, col):
        if not col: return ""
        parts = col.split('.')
        name = parts[1] if len(parts) > 1 else parts[0]
        return name.replace('_', ' ').title()

# Singleton
ticker_service = TickerService()
