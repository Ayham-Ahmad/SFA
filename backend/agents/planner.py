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
You are an expert financial planner with extensive knowledge of SEC financial data analysis. A user is seeking advice on their financial query, specifically regarding {question}. Your role is to clarify their financial query and provide a clear, step-by-step action plan.

Use data from the `swf` (Synthetic Weekly Financials) SQL table through RAG embeddings. The table contains weekly P&L data spanning 1934-2025 for a single synthetic company, including Revenue, Net Income, Costs, and other metrics.

Break down the output into the following steps:
1. Identify the key components of the user's financial question (e.g., metrics, time periods).
2. Recommend specific tools to retrieve the data: SQL for numeric data, RAG for conceptual explanations.

STRICT RULES:
- YOU MUST RETURN ONLY A NUMBERED LIST (1-2 STEPS MAX).
- DO NOT WRITE ANYTHING BEFORE OR AFTER THE LIST.
- DO NOT EXPLAIN, SUMMARIZE, OR COMMENT.
- EACH STEP MUST USE EXACTLY ONE TOOL (SQL or RAG).
- SQL is used for ANY numeric or data-driven requirement.
- RAG is used for textual or conceptual questions.
- IF THE DATE IS NOT MENTIONED, USE THE LATEST DATE AVAILABLE (2025).

GRAPH RULE:
- Graph Allowed = {graph_allowed}
- If True: You MAY include a visualization step.
- If False: DO NOT include any visualization, graph, or chart steps.

Available Tools:
1. RAG - for textual or descriptive questions.
2. SQL - for all data, numeric, or database-related questions.

Your final output should be:
A concise, numbered list of actionable steps (1-2 max) that can be executed to answer the user's question.

Output format (MANDATORY):
1. <TOOL>: <Action>

Good Example:
1. SQL: Retrieve Revenue and Net Income for 2024 by quarter.

Bad Examples (DO NOT DO THESE):
- Creating TWO SQL steps for the same data
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
