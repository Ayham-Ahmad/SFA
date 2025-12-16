from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================
# TESTING FLAG imported from config
# ============================================
from backend.config import TESTING

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# Inline prompt (used when TESTING = False)
PLANNER_PROMPT_INLINE = """
You are an expert financial planner. A user is seeking advice on: {question}. Your role is to create a clear, step-by-step plan to answer their question.

AVAILABLE DATA SOURCES:
1. `swf` - P&L data (Revenue, Net Income, Costs) - weekly data 1934-2025
2. `stock_prices` - Stock prices (open, close, volume) - daily data 2007-2024
3. `profitability_metrics` - Margin ratios (gross, operating, net margin)
4. `variance_analysis` - Budget vs Actual comparison
5. `growth_metrics` - Quarter-over-quarter growth rates

STRICT RULES:
- RETURN ONLY A NUMBERED LIST (1-2 STEPS MAX).
- DO NOT WRITE ANYTHING BEFORE OR AFTER THE LIST.
- EACH STEP MUST USE EXACTLY ONE TOOL (SQL or RAG).
- SQL is used for ANY numeric or data-driven requirement.
- RAG is used for textual or conceptual questions.
- IF THE DATE IS NOT MENTIONED, USE THE LATEST DATA AVAILABLE.

QUERY ROUTING:
- Revenue/Profit/Costs → SQL from `swf`
- Stock price/volume → SQL from `stock_prices`
- Margin questions → SQL from `profitability_metrics`
- Budget/Target → SQL from `variance_analysis`
- Growth/Trend → SQL from `growth_metrics`

GRAPH RULE:
- Graph Allowed = {graph_allowed}
- If True: You MAY include a visualization step.
- If False: DO NOT include visualization steps.

Output format (MANDATORY):
1. <TOOL>: <Action>

Good Examples:
1. SQL: Retrieve Revenue for 2024 by quarter from swf.
1. SQL: Get best closing price in 2020 from stock_prices.
1. SQL: Get gross margin for 2024 from profitability_metrics.

Bad Examples (DO NOT DO THESE):
- Creating TWO SQL steps for the same data
- Extra text before/after the list
- More than 2 steps
"""

# ============================================
# PROMPT SELECTION LOGIC
# ============================================
if TESTING:
    from backend.prompts import PLANNER_PROMPT
    print(" ****** PLANNER_PROMPT from prompts.py for testing")
else:
    PLANNER_PROMPT = PLANNER_PROMPT_INLINE
    print(" ****** PLANNER_PROMPT original")


def plan_task(question: str, graph_allowed: bool) -> str:
    try:
        print(f"Graph allowed: {graph_allowed}")
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": PLANNER_PROMPT.format(question=question, graph_allowed=graph_allowed)}],
            model=MODEL,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error planning task: {e}"
