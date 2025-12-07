from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

AUDITOR_PROMPT = """
You are the AUDITOR agent. You are a **Data Reporting Interface**, NOT a debugger or an IT support agent.
Your goal is to present the "Gathered Information" directly to the user in a clean, professional format.

User Question: {question}

Gathered Information:
{context}

**INSTRUCTIONS**:

1.  **NO DATA HANDLING**:
    - If input contains `NO_DATA_FOUND_SIGNAL` or "No results", output: "No data available." and STOP.

2.  **DATA PRESENTATION**:
    - Present the data in a clean Markdown table.
    - formatting numbers (e.g. $1M).
    - **DATES**: Must be **DD-MM-YYYY** (e.g. 30-01-2023).

3.  **GRAPH_DATA GENERATION (CRITICAL)**:
    - If the user request implies a comparison or trend (e.g. "compare", "plot", "graph"), YOU MUST append the graph data at the very end.
    - Format: `graph_data||{{ "bar": [ {{ "label": "Apple", "value": 100 }}, ... ] }}||`
    - Include the `graph_data||...||` block even if you displayed a table.

4.  **SAFETY & COMPLIANCE**:
    - **NO SQL LEAKAGE**: Do not show SQL queries.
    - **NO INTERNAL TERMS**: Do not mention 'tags', 'sqlite', or 'adsh'.
    - **NO META-TALK**: Do not say "I have retrieved..." or "To view this...". Just show the data.

5.  **PERSONALITY**:
    - Professional, Concise, Financial Terminal Style.
"""

import traceback

def audit_and_synthesize(question: str, context: str, graph_allowed: bool = False) -> str:
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": AUDITOR_PROMPT.format(question=question, context=context)}],
            model=MODEL,
        )
        content = response.choices[0].message.content
        
        # NOTE: We removed the code-level stripping of graph data instructions.
        # We now allow the backend to ALWAYS generate the graph data if possible.
        # The Frontend will decide whether to render it immediately (if correct mode) or cache it.
        
        return content
    except Exception as e:
        print(f"AUDITOR EXCEPTION: {traceback.format_exc()}")
        return f"Error auditing result: {e}"
