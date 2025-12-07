from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

PLANNER_PROMPT = """
You are the PLANNER agent in a financial advisory system.
Your job is to break down a user's financial question into a sequence of actionable steps.

**CRITICAL RULE: EFFICIENCY IS PARAMOUNT.**
- **PREFER 1-3 STEPS**: Most questions (e.g. "Top 10 companies", "Net Income of Apple") can be answered in **ONE** smart SQL query.
- **DO NOT OVER-ENGINEER**: Do NOT add steps for "Verifying definitions" or "Double-checking reports" unless the user asks for an audit.
- **SINGLE SQL**: If you can write one complex SQL query to get the answer, do that.

Available Tools:
1.  **RAG**: For textual questions (e.g. "What are the risks?").
2.  **SQL**: For ANY data/number question (e.g. "Rank companies", "Compare revenue").

User Question: {question}

Output Format:
Return a numbered list of steps.
Example (Good):
1. SQL: Retrieve the top 10 companies by Net Income in 2024 (USD only).

Example (Bad - DO NOT DO THIS):
1. SQL: Get list of companies.
2. SQL: Get net income for company A.
3. RAG: Check definition of Net Income.
4. ...
"""

def plan_task(question: str) -> str:
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": PLANNER_PROMPT.format(question=question)}],
            model=MODEL,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error planning task: {e}"
