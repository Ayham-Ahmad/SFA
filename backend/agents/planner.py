"""
Planner Agent
=============
Decomposes user questions into actionable SQL steps.
"""
from backend.utils.llm_client import groq_client, get_model
from backend.sfa_logger import log_system_debug, log_system_error

MODEL = get_model("default")

PLANNER_PROMPT = """
You are the Planner Agent for a Smart Financial Advisor.

Your task is to create a short execution plan to answer the user question.

AVAILABLE TOOLS:
- SQL → Use for ANY numeric, financial, trend, comparison, or time-based question.
- ADVISORY → Use for strategic questions, recommendations, or "should we" decisions.

AVAILABLE DATA:
1) swf_financials
   - Quarterly financial data (revenue, costs, income, margins)
   - One virtual, market-representative entity

ROUTING RULES:
- "What is/was X?" → SQL
- "Show me / Compare / Trend" → SQL
- "Should we / Recommend / Strategy / Improve / Focus" → ADVISORY

RULES:
- Output ONLY a numbered list (max 2 steps).
- Each step MUST use exactly one tool.
- Do NOT explain the plan.
- If time is not specified, use the most recent data.

GRAPH CONTROL:
- graph_allowed = {graph_allowed}
- If false, DO NOT include visualization steps.

FORMAT (MANDATORY):
1. <TOOL>: <Action>

Examples:
1. SQL: Retrieve quarterly net income for 2024 from swf_financials.
1. SQL: Compare revenue trend for the last 3 years.
1. ADVISORY: Provide strategic recommendation on cost reduction vs revenue growth.

User question: {question}
"""


def plan_task(question: str, graph_allowed: bool, schema_context: str = "") -> str:
    """
    Create an execution plan to answer the user's question.
    
    Args:
        question: User's question
        graph_allowed: Whether graph generation is allowed
        schema_context: Summary of available database schema
        
    Returns:
        Numbered list of steps (SQL/ADVISORY)
    """
    try:
        log_system_debug(f"Planner - Graph allowed: {graph_allowed}")
        
        # Format the prompt
        prompt_content = PLANNER_PROMPT.format(
            question=question, 
            graph_allowed=graph_allowed,
            schema_context=schema_context
        )
        
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt_content}],
            model=MODEL,
        )
        return response.choices[0].message.content
    except Exception as e:
        log_system_error(f"Error planning task: {e}")
        return f"Error planning task: {e}"
