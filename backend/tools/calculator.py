"""
Calculator Tool
===============
Provides safe mathematical evaluation for financial data arrays.
Wraps Python's eval() in a restricted scope to prevent code execution attacks.
"""
from typing import List, Dict, Union, Any
import pandas as pd
import numpy as np
from langchain_core.tools import Tool

def safe_calculate(expression: str, data_context: List[Dict[str, Any]] = None) -> str:
    """
    Evaluates a math expression on a dataset.
    
    Args:
        expression: Python-like expression (e.g. "(df['revenue'] - df['cost']) / 100")
        data_context: List of dicts (rows) from a previous SQL query.
        
    Returns:
        JSON string with the calculated results added to the dataset.
    """
    try:
        # Strip surrounding quotes if present (LLM sometimes wraps expression in quotes)
        expression = expression.strip()
        if (expression.startswith("'") and expression.endswith("'")) or \
           (expression.startswith('"') and expression.endswith('"')):
            expression = expression[1:-1]
        
        # Sanitize: remove $ symbols and convert B/M/K to actual numbers
        import re
        expression = expression.replace('$', '')
        # Convert 4.58B to 4580000000, 814.08M to 814080000, etc.
        expression = re.sub(r'(\d+\.?\d*)B', lambda m: str(float(m.group(1)) * 1e9), expression, flags=re.I)
        expression = re.sub(r'(\d+\.?\d*)M', lambda m: str(float(m.group(1)) * 1e6), expression, flags=re.I)
        expression = re.sub(r'(\d+\.?\d*)K', lambda m: str(float(m.group(1)) * 1e3), expression, flags=re.I)
        
        if not data_context:
            # Simple scalar math
            allowed_names = {"abs": abs, "round": round, "min": min, "max": max}
            result = eval(expression, {"__builtins__": None}, allowed_names)
            return f"Result: {result}"
            
        # DataFrame Math
        df = pd.DataFrame(data_context)
        if df.empty:
            return "Error: No data available to calculate on."

        # create local scope with safe numpy/pandas functions
        local_scope = {
            "df": df,
            "np": np,
            "pd": pd,
            "abs": abs,
            "round": round
        }
        
        # We expect the expression to either return a series/value OR modify 'df'
        # Example input: "df['profit_margin'] = (df['revenue'] - df['cost']) / df['revenue']"
        # Or just: "(df['revenue'] - df['cost']).mean()"
        
        # If expression is an assignment, exec it. If value, eval it.
        if "=" in expression and not "==" in expression:
            exec(expression, {"__builtins__": None}, local_scope)
            result_df = local_scope['df']
            # Limit rows for output
            return result_df.head(20).to_json(orient="records", date_format="iso")
        else:
            result = eval(expression, {"__builtins__": None}, local_scope)
            return str(result)

    except Exception as e:
        return f"Calculation Error: {e}"

def get_calculator_tool(data_context_getter, query_id_getter=None) -> Tool:
    """
    Factory to create a calculator tool that has access to the agent's current data context.
    
    Args:
        data_context_getter: Function that returns the most recent SQL result (List[Dict]).
        query_id_getter: Optional function that returns the current query_id for progress updates.
    """
    from backend.core.logger import log_system_debug, log_agent_interaction
    from backend.pipeline.progress import set_query_progress
    
    def run_calc(expression: str) -> str:
        # Update status for frontend
        if query_id_getter:
            query_id = query_id_getter()
            if query_id:
                set_query_progress(query_id, "calculator", "🧮 Calculating...")
        
        log_system_debug(f"[Calculator] Evaluating: {expression}")
        data = data_context_getter()
        result = safe_calculate(expression, data)
        log_system_debug(f"[Calculator] Result: {result[:200] if len(result) > 200 else result}")
        return result

    return Tool(
        name="calculator",
        func=run_calc,
        description="Performs simple mathematical calculations. Input must be a valid Python math expression. Use raw numbers only - do NOT include $ symbols or B/M/K suffixes. Examples: '(4580000000 - 1430000000) / 1430000000 * 100' or 'round(2.5 / 1.2, 2)'. Only use numbers and operators (+, -, *, /, round, abs, min, max)."
    )
