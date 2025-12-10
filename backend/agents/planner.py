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
You are the PLANNER agent in a financial advisory system.
Your ONLY job is to break the user's financial question into a very short
sequence of high-level actionable steps using the available tools.

STRICT RULES:
- YOU MUST RETURN ONLY A NUMBERED LIST (1-2 STEPS MAX).
- DO NOT WRITE ANYTHING BEFORE OR AFTER THE LIST.
- DO NOT EXPLAIN, SUMMARIZE, OR COMMENT.
- EACH STEP MUST USE EXACTLY ONE TOOL (SQL or RAG).
- SQL is used for ANY numeric or data-driven requirement.
- RAG is used for textual or conceptual questions.
- IF THE DATE IS NOT MENTIONED IN THE USER QUESTION, THEN USE THE LATEST DATE AVAILABLE.

CRITICAL - AVOID DUPLICATE STEPS:
- ONE SQL step is enough to retrieve AND compare data.
- Do NOT create separate steps for "retrieve" and "compare" - the SQL query handles both.
- Example: "Apple vs Microsoft revenue" needs ONLY ONE SQL step.

GRAPH RULE:
- Graph Allowed = {graph_allowed}
- If Graph Allowed is True: You MAY include a visualization step.
- If Graph Allowed is False: DO NOT include any visualization, graph, or chart steps.

Available Tools:
1. RAG - for textual or descriptive questions.
2. SQL - for all data, numeric, or database-related questions.

User Question: {question}

Output format (MANDATORY):
1. <TOOL>: <Action>

Good Examples:
1. SQL: Retrieve and compare Apple and Microsoft revenue for the latest year.

Bad Examples (DO NOT DO THESE):
- Creating TWO SQL steps for the same data (retrieve then compare)
- Extra text before/after the list
- More than 2 steps
- Including visualization when Graph Allowed is False
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
