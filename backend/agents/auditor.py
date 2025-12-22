from groq import Groq
import os
from dotenv import load_dotenv
import traceback
from backend.sfa_logger import log_system_debug, log_system_error, log_system_info, log_agent_interaction
from backend.config import TESTING

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Inline prompts (used when TESTING = False)
# TEXT-ONLY prompt (no graph instructions) - CONCISE VERSION
TEXT_PROMPT_INLINE = """
You are a Financial Reporting Assistant.

Answer the user's question using ONLY the provided data.

RULES:
1. Use ONLY the values shown.
2. Do NOT estimate or extrapolate.
3. Do NOT mention databases, SQL, or internal systems.
4. If data is unavailable, say: "Data not available for this period."
5. Margins are decimals → convert to percentages.

STYLE:
- 2–3 sentences max
- One small table if helpful
- Financial units:
  - Billions → $XX.XXB
  - Millions → $XX.XXM

User question: {question}
Data:
{context}
"""

# GRAPH prompt - Plotly.js format with concise output
GRAPH_PROMPT_INLINE = """
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

GRAPH_SELECTION_LOGIC_INLINE = """
Determine the best chart type based on intent:
- Time-based → Line
- Comparison → Bar
- Composition → Pie
- Single KPI → Card

Default → Line
"""

# ============================================
# PROMPT SELECTION LOGIC
# ============================================
if TESTING:
    from backend.prompts import TEXT_PROMPT, GRAPH_PROMPT, GRAPH_SELECTION_LOGIC
else:
    TEXT_PROMPT = TEXT_PROMPT_INLINE
    GRAPH_PROMPT = GRAPH_PROMPT_INLINE
    GRAPH_SELECTION_LOGIC = GRAPH_SELECTION_LOGIC_INLINE


def audit_and_synthesize(question: str, context: str, graph_allowed: bool = False, interaction_id: str = None) -> str:
    """
    Synthesizes the final answer from gathered context.
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
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": full_prompt}],
            model=MODEL,
            temperature=0.3,
            max_tokens=2000
        )
        content = response.choices[0].message.content
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
