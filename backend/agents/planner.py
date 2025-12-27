"""
Planner Agent
=============
Decomposes user questions into actionable SQL steps.
Supports user-specific database schemas for multi-tenant operation.
"""
from backend.utils.llm_client import groq_client, get_model
from backend.sfa_logger import log_system_debug, log_system_error

MODEL = get_model("default")


def get_planner_prompt(user=None, graph_allowed=False):
    """
    Build planner prompt with user-specific schema if available.
    
    Args:
        user: Optional User model instance
        graph_allowed: Whether graphs are allowed
        
    Returns:
        Formatted planner prompt string
    """
    # Get available data description - REQUIRE database connection
    if user and user.db_is_connected:
        # User has their own database - get dynamic schema
        from backend.tools.sql_tools import get_table_schemas
        schema = get_table_schemas(user=user)
        available_data = f"""AVAILABLE DATA (User's Connected Database):
{schema}

Note: Query the user's connected database tables shown above."""
    else:
        # No database connected
        available_data = """AVAILABLE DATA:
⚠️ NO DATABASE CONNECTED
Please connect a database in Settings before querying data."""
    
    return f"""You are the Planner Agent for a Smart Financial Advisor.

Your task is to create a SHORT execution plan to answer the user question.

AVAILABLE TOOLS:
- SQL → Use for ANY numeric, data lookup, trend, comparison, or time-based question.
- ADVISORY → Use for strategic questions, recommendations, or "should we" decisions.

{available_data}

ROUTING RULES:
- "What is/was X?" → SQL (1 step only)
- "Show me / Compare / Trend" → SQL (1 step only)
- "Should we / Recommend / Strategy" → ADVISORY (1 step only)
- Complex analysis needing data + recommendation → SQL then ADVISORY (2 steps max)

CRITICAL RULES:
- Output ONLY a numbered list.
- For simple data queries, use EXACTLY 1 step.
- Do NOT add error handling steps (like "if no data found...").
- Do NOT explain the plan.
- Maximum 2 steps total.
- If time is not specified, use the most recent data.

GRAPH CONTROL:
- graph_allowed = {graph_allowed}
- If false, DO NOT include visualization steps.

FORMAT (MANDATORY):
1. <TOOL>: <Action>

Examples:
1. SQL: Retrieve quarterly net income for 2024.
1. SQL: Get the latest open price from the database.
1. ADVISORY: Provide strategic recommendation on cost reduction.
"""


def plan_task(question: str, graph_allowed: bool, user=None) -> str:
    """
    Create an execution plan to answer the user's question.
    
    Args:
        question: User's question
        graph_allowed: Whether graph generation is allowed
        user: Optional User model instance for tenant-specific schema
        
    Returns:
        Numbered list of steps (SQL/ADVISORY)
    """
    try:
        log_system_debug(f"Planner - Graph allowed: {graph_allowed}, User: {user.id if user else 'None'}")
        
        prompt = get_planner_prompt(user=user, graph_allowed=graph_allowed)
        prompt += f"\nUser question: {question}"
        
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL,
        )
        return response.choices[0].message.content
    except Exception as e:
        log_system_error(f"Error planning task: {e}")
        return f"Error planning task: {e}"

