from groq import Groq
import os
from dotenv import load_dotenv
import traceback

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# TEXT-ONLY prompt (no graph instructions) - CONCISE VERSION
TEXT_PROMPT = """
You are a Financial Data Reporter. Give ONLY the essential facts.

Question: {question}

Data:
{context}

OUTPUT RULES:
1. BE EXTREMELY CONCISE - 2-3 sentences max for narrative.
2. ONE simple table if showing numbers.
3. Use format: $XXX.XXB for billions, $XXX.XXM for millions.
4. NO repetition of the same data.
5. NO sections like "Key Insights", "Comparison", "Summary" - just answer directly.
6. If no data: "Data not available for this query."
7. DO NOT mention SQL, databases, queries, or any technical details.
8. Include the data date/period if available.

BAD EXAMPLE (too verbose):
"Here is a summary... The latest revenue... Key insights... In conclusion..."

GOOD EXAMPLE:
"Apple's revenue for Q1 2025: $219.66B. Microsoft's revenue: $205.28B.
| Company | Revenue |
| Apple | $219.66B |
| Microsoft | $205.28B |"
"""

# GRAPH prompt - Plotly.js format with concise output
GRAPH_PROMPT = """
You generate Plotly.js charts from financial data.

Question: {question}
Data: {context}

OUTPUT FORMAT (STRICT):
1. Text Response: Write ONLY "Graph generated." (nothing else, no tables, no explanations)
2. Graph Code: graph_data||<PLOTLY_JSON>||

PLOTLY JSON FORMAT (MANDATORY - DO NOT USE CHART.JS):
{{
  "data": [
    {{"x": ["Label1", "Label2"], "y": [value1, value2], "type": "bar", "name": "Series Name"}}
  ],
  "layout": {{"title": "Chart Title"}}
}}

CHART TYPES:
- "bar" for comparisons
- "scatter" with "mode": "lines+markers" for trends
- "pie" for percentages

EXAMPLE OUTPUT:
Graph generated.

graph_data||{{"data":[{{"x":["Apple","Microsoft"],"y":[219659000000,205283000000],"type":"bar","name":"Revenue"}}],"layout":{{"title":"Revenue Comparison 2025"}}}}||

RULES:
- Use ONLY Plotly.js format (with "data" and "layout" keys)
- DO NOT use Chart.js format (labels/datasets)
- Output ONLY "Graph generated." as text - NO tables, NO explanations
- Values in "y" must be raw numbers, not strings
"""

GRAPH_SELECTION_LOGIC = """

When the user does NOT specify a chart type:
1. Analyze the intent of the question based on:
   - Profitability Flow
   - Comparative Analysis
   - Composition/Breakdown
   - Time Trend

2. Select chart according to the Graph Decision Matrix:

- Bar/Column → Compare categories or for time-based bars.
- Line/Area → Time trends by date.
- Pie/Donut → Part-to-whole breakdown.
- Card → Single KPI.
- Table → Detailed granular values.
- Scatter → Relationship between two numeric measures.
- Waterfall → Changes from start to end (contributions).

If no match is found: default to a bar chart.

Perform all reasoning internally and do NOT reveal it.

"""


def audit_and_synthesize(question: str, context: str, graph_allowed: bool = False, interaction_id: str = None) -> str:
    """
    Synthesizes the final answer from gathered context.
    """
    try:
        print(f"\nAuditor Synthesizing: {question}")
        # Log input
        if interaction_id:
            from backend.agent_debug_logger import log_agent_interaction
            log_agent_interaction(interaction_id, "Auditor", "Input", {
                "question": question,
                "context_provided": context
            }, None)

        # CONDITIONAL: Use different prompts based on request type
        if graph_allowed:
            full_prompt = GRAPH_PROMPT.format(question=question, context=context) + "\n" + GRAPH_SELECTION_LOGIC
            print(f"Auditor Synthesizing with Graph: {full_prompt}")
        else:
            full_prompt = TEXT_PROMPT.format(question=question, context=context)
            print(f"Auditor Synthesizing without Graph: {full_prompt}")
        
        # Call the LLM
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model=MODEL,
            temperature=0.3,
            max_tokens=2000
        )
        content = response.choices[0].message.content
        print(f"Auditor Synthesizing Result: {content}")
        
        # Log output
        if interaction_id:
            from backend.agent_debug_logger import log_agent_interaction
            log_agent_interaction(interaction_id, "Auditor", "Output", None, content)
        
        # If graph not allowed, strip any graph data from response
        if not graph_allowed and "graph_data||" in content:
            content = content.split("graph_data||")[0].strip()
            print(f"Auditor Synthesizing Result without Graph: {content}")
        
        return content
        
    except Exception as e:
        print(f"AUDITOR EXCEPTION: {traceback.format_exc()}")
        return f"Error auditing result: {e}"
