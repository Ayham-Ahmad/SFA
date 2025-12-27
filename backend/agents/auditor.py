"""
Auditor Agent
=============
Synthesizes final answers from gathered context.
"""
from backend.utils.llm_client import groq_client, get_model
from backend.sfa_logger import log_system_debug, log_system_error, log_system_info, log_agent_interaction
import traceback

MODEL = get_model("auditor")

# Graph Selection Logic - Decision framework for chart type selection
GRAPH_SELECTION_LOGIC = """
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

# TEXT-ONLY prompt (no graph instructions) - CONCISE VERSION
TEXT_PROMPT = """
You are a Financial Reporting Assistant.

Answer the user's question using ONLY the provided data.

RULES:
1. Use ONLY the values shown - report them exactly as they appear.
2. Do NOT estimate, extrapolate, or assume units.
3. Do NOT mention databases, SQL, or internal systems.
4. If data is unavailable, say: "Data not available for this period."
5. If the value has no clear unit context, report the raw number.

STYLE:
- 2–3 sentences max
- One small table if helpful
- Only add units ($, B, M) if the data clearly indicates them

User question: {question}
Data:
{context}
"""

# GRAPH prompt - Plotly.js format with concise output
GRAPH_PROMPT = """
Your task is to generate a Plotly.js visualization.

INPUT:
Question: {question}
Data: {context}

RULES:
- Output EXACTLY:
  1) Text: "Graph generated."
  2) Plotly JSON prefixed by: graph_data||
- Use numeric values only.
- No explanations, no tables.

CHART GUIDELINES:
- Line → time trends
- Bar → comparisons
- Pie → composition

OUTPUT FORMAT:
Graph generated.
graph_data||{{PLOTLY_JSON}}||
"""


def audit_and_synthesize(question: str, context: str, graph_allowed: bool = False, interaction_id: str = None) -> str:
    """
    Synthesizes the final answer from gathered context.
    
    Args:
        question: User's original question
        context: Context gathered from SQL execution
        graph_allowed: Whether graph generation is allowed
        interaction_id: Optional ID for logging
        
    Returns:
        Synthesized answer text (may include graph_data||...|| if graph_allowed)
    """
    try:
        log_system_debug(f"Auditor Synthesizing: {question}")
        
        # Log input
        if interaction_id:
            log_agent_interaction(interaction_id, "Auditor", "Input", {
                "question": question,
                "context_provided": context
            }, None)

        # CONDITIONAL: Use different prompts based on request type
        if graph_allowed:
            full_prompt = GRAPH_PROMPT.format(question=question, context=context) + "\n" + GRAPH_SELECTION_LOGIC
            log_system_debug(f"Auditor Synthesizing with Graph: {full_prompt}")
        else:
            full_prompt = TEXT_PROMPT.format(question=question, context=context)
            log_system_debug(f"Auditor Synthesizing without Graph: {full_prompt}")
        
        # Call the LLM
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model=MODEL,
            temperature=0.3,
            max_tokens=2000
        )
        content = response.choices[0].message.content
        
        # Strip thinking tags from models that expose reasoning (like DeepSeek)
        if "<think>" in content:
            import re
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        
        log_system_debug(f"Auditor Synthesizing Result: {content}")
        
        # Validation: If graph was required but not produced, BUILD IT PROGRAMMATICALLY
        if graph_allowed and "graph_data||" not in content:
            log_system_info(f"⚠️ WARNING: Graph generation was required but LLM didn't produce it. Building programmatically...")
            
            try:
                from backend.tools.graph_builder import build_graph_from_context
                
                # Build graph from the context (SQL results)
                graph_json = build_graph_from_context(context, question)
                
                if graph_json:
                    log_system_info(f"✅ Graph built programmatically!")
                    # Append graph data to content
                    content = content.rstrip() + f"\n\ngraph_data||{graph_json}||"
                else:
                    log_system_info(f"❌ No graphable data found in context")
            except Exception as e:
                log_system_error(f"❌ Programmatic graph building failed: {e}")
        
        # Log output
        if interaction_id:
            log_agent_interaction(interaction_id, "Auditor", "Output", None, content)
        
        # If graph not allowed, strip any graph data from response
        if not graph_allowed and "graph_data||" in content:
            content = content.split("graph_data||")[0].strip()
            log_system_debug(f"Auditor Synthesizing Result without Graph: {content}")
        
        return content
        
    except Exception as e:
        log_system_error(f"AUDITOR EXCEPTION: {traceback.format_exc()}")
        return f"Error auditing result: {e}"
