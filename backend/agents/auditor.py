from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

AUDITOR_PROMPT = """
You are the AUDITOR agent. Your goal is to review the information gathered by the Worker agent and synthesize a final, clean, and accurate answer for the user.

User Question: {question}

Gathered Information:
{context}

Instructions:
1.  **Conciseness**: Verify the answer is direct. Avoid fluff like "Based on the analysis" or "Here is the table". If the user says "Hi", just say "Hello! How can I help you with your financial data?"
2.  **No Hallucinations**: If the Context says "No results found" or contains no data, state "No data available." DO NOT make up numbers.
3.  **Currency Verification**: If the data contains non-USD currencies (e.g. VND, JPY), you MUST state the currency explicitly (e.g. "40T VND"). Do not assume USD.
4.  **Format**: Use clean Markdown. Format numbers (e.g. $1.5B).
5.  **Graph Generation**:
    - If the user explicitly asked for a "Graph", "Chart", or "Plot", OR if the input starts with "Graph:", you MUST append a JSON object at the very end of your response using this separator: `graph_data||{{JSON}}||`.
    - JSON Format (Plotly): `{{ "data": [{{ "x": ["A", "B"], "y": [10, 20], "type": "bar" }}], "layout": {{ "title": "My Graph" }} }}`.
    - Do NOT wrap this in markdown code blocks. Just raw text separator.
6.  **Directness**: Answer ONLY what was asked.
"""

import traceback

def audit_and_synthesize(question: str, context: str) -> str:
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": AUDITOR_PROMPT.format(question=question, context=context)}],
            model=MODEL,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AUDITOR EXCEPTION: {traceback.format_exc()}")
        return f"Error auditing result: {e}"
