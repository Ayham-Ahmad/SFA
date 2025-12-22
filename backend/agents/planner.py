from groq import Groq
import os
from dotenv import load_dotenv
from backend.sfa_logger import log_system_debug, log_system_error
from backend.config import TESTING

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# Inline prompt (used when TESTING = False)
PLANNER_PROMPT_INLINE = """
You are the Planner Agent for a Smart Financial Advisor.

Your task is to create a short execution plan to answer the user question.

AVAILABLE TOOLS:
- SQL → Use for ANY numeric, financial, trend, comparison, or time-based question.
- RAG → Use ONLY for definitions, explanations, or non-data concepts.
- ADVISORY → Use for strategic questions, recommendations, or "should we" decisions.

AVAILABLE DATA:
1) swf_financials
   - Quarterly financial fundamentals (2012–2025)
   - One virtual, market-representative entity
   - Metrics: revenue, costs, income, margins

2) market_daily_data
   - Daily market signals (returns, volatility)
   - Used ONLY when market behavior is explicitly requested

ROUTING RULES:
- "What is/was X?" → SQL
- "Show me / Compare / Trend" → SQL
- "Should we / Recommend / Strategy / Improve / Focus" → ADVISORY
- "What does X mean?" → RAG

RULES:
- Output ONLY a numbered list (max 2 steps).
- Each step MUST use exactly one tool.
- Do NOT explain the plan.
- If time is not specified, use the most recent data.
- Do NOT reference companies or tickers.

GRAPH CONTROL:
- graph_allowed = {graph_allowed}
- If false, DO NOT include visualization steps.

FORMAT (MANDATORY):
1. <TOOL>: <Action>

Examples:
1. SQL: Retrieve quarterly net income for 2024 from swf_financials.
1. SQL: Compare revenue trend and average market volatility for 2023.
1. ADVISORY: Provide strategic recommendation on cost reduction vs revenue growth.

User question: {question}
"""

# ============================================
# PROMPT SELECTION LOGIC
# ============================================
if TESTING:
    from backend.prompts import PLANNER_PROMPT
else:
    PLANNER_PROMPT = PLANNER_PROMPT_INLINE


def plan_task(question: str, graph_allowed: bool) -> str:
    try:
        log_system_debug(f"Planner - Graph allowed: {graph_allowed}")
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": PLANNER_PROMPT.format(question=question, graph_allowed=graph_allowed)}],
            model=MODEL,
        )
        return response.choices[0].message.content
    except Exception as e:
        log_system_error(f"Error planning task: {e}")
        return f"Error planning task: {e}"
