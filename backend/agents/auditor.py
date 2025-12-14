from groq import Groq
import os
from dotenv import load_dotenv
import traceback

load_dotenv()

# ============================================
# TESTING FLAG imported from config
# ============================================
from backend.config import TESTING

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Inline prompts (used when TESTING = False)
# TEXT-ONLY prompt (no graph instructions) - CONCISE VERSION
TEXT_PROMPT_INLINE = """
You are a Financial Data Reporter. Give ONLY the essential facts.

Question: {question}

Data:
{context}

DATA SELECTION RULES (CRITICAL):
1. If multiple values exist for the SAME date/year (e.g., multiple 2024 or 2025 entries):
   - Use the FIRST/TOP value for each year (it's already sorted by date DESC)
   - DO NOT sum or aggregate multiple values
   - DO NOT use random middle values
2. For year-over-year comparisons, pick ONE value per year consistently.

OUTPUT RULES:
1. BE EXTREMELY CONCISE - 2-3 sentences max for narrative.
2. ONE simple table if showing numbers.
3. Use format: $XXX.XXB for billions, $XXX.XXM for millions.
4. NO repetition of the same data.
5. NO sections like "Key Insights", "Comparison", "Summary" - just answer directly.
6. If no data: "Data not available for this query."
7. DO NOT mention SQL, databases, queries, or any technical details.
8. Include the data date/period if available.
9. Use ONLY the values that appear in the data - DO NOT calculate or estimate.

BAD EXAMPLE (too verbose):
"Here is a summary... The latest revenue... Key insights... In conclusion..."

GOOD EXAMPLE:
"Apple's revenue for Q1 2025: $219.66B. Microsoft's revenue: $205.28B.
| Company | Revenue |
| Apple | $219.66B |
| Microsoft | $205.28B |"
"""

# GRAPH prompt - Plotly.js format with concise output
GRAPH_PROMPT_INLINE = """
**CRITICAL OVERRIDE INSTRUCTION:**
You MUST generate a graph for THIS request. This is a MANDATORY graph generation task.
Previous responses in the context are provided ONLY for reference and continuity.
DO NOT let historical response patterns (e.g., previous table-only responses) influence your current output.
Your ONLY task NOW is to create a Plotly.js chart using the data provided.

You generate Plotly.js charts from financial data.

Question: {question}
Data: {context}

DATA SELECTION RULES (CRITICAL):
1. If multiple values exist for the SAME date/year:
   - Use the FIRST/TOP value for each year (data is sorted by date DESC)
   - DO NOT sum, aggregate, or estimate values
   - Pick ONE consistent value per year/category
2. Use ONLY values that actually appear in the data.

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

GRAPH_SELECTION_LOGIC_INLINE = """
I require a decision-making framework for selecting appropriate chart types based on user queries that do not specify a chart type. The output should include the following structured analysis:

1. An evaluation of the user's intent categorized under:
   - Profitability Flow
   - Comparative Analysis
   - Composition/Breakdown
   - Time Trend

2. A recommended chart type based on the Graph Decision Matrix, considering:
   - Bar/Column → for comparing categories or displaying time-based data.
   - Line/Area → for illustrating time trends by date.
   - Pie/Donut → for demonstrating part-to-whole relationships.
   - Card → for showcasing a single KPI.
   - Table → for presenting detailed granular values.
   - Scatter → for analyzing the relationship between two numeric measures.
   - Waterfall → for visualizing changes from start to end, highlighting contributions.

If no clear match is identified, default to recommending a bar chart.

Ensure that all reasoning is conducted internally and not disclosed in the output.

For context, I am focusing on generating visualizations that cater to an audience with varying levels of data literacy, and the final output should be straightforward and intuitive.
"""

# ============================================
# PROMPT SELECTION LOGIC
# ============================================
if TESTING:
    from backend.prompts import TEXT_PROMPT, GRAPH_PROMPT, GRAPH_SELECTION_LOGIC
    print(" ****** TEXT_PROMPT, GRAPH_PROMPT from prompts.py for testing")
else:
    TEXT_PROMPT = TEXT_PROMPT_INLINE
    GRAPH_PROMPT = GRAPH_PROMPT_INLINE
    GRAPH_SELECTION_LOGIC = GRAPH_SELECTION_LOGIC_INLINE
    print(" ****** TEXT_PROMPT, GRAPH_PROMPT original")


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
        
        # Validation: If graph was required but not produced, BUILD IT PROGRAMMATICALLY
        if graph_allowed and "graph_data||" not in content:
            print(f"⚠️ WARNING: Graph generation was required but LLM didn't produce it. Building programmatically...")
            
            try:
                from backend.tools.graph_builder import build_graph_from_context
                
                # Build graph from the context (SQL results)
                graph_json = build_graph_from_context(context, question)
                
                if graph_json:
                    print(f"✅ Graph built programmatically!")
                    # Append graph data to content
                    content = content.rstrip() + f"\n\ngraph_data||{graph_json}||"
                else:
                    print(f"❌ No graphable data found in context")
            except Exception as e:
                print(f"❌ Programmatic graph building failed: {e}")
        
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
