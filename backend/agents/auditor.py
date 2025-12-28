"""
Auditor Agent
=============
Synthesizes final answers from gathered context.
Text-only responses - graphs are handled by a separate pipeline.
"""
from backend.utils.llm_client import groq_client, get_model
from backend.core.logger import log_system_debug, log_system_error, log_agent_interaction
import traceback

MODEL = get_model("auditor")

# TEXT-ONLY prompt - CONCISE VERSION
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


def audit_and_synthesize(question: str, context: str, interaction_id: str = None) -> str:
    """
    Synthesizes the final answer from gathered context.
    
    Args:
        question: User's original question
        context: Context gathered from SQL execution
        interaction_id: Optional ID for logging
        
    Returns:
        Synthesized text answer
    """
    try:
        log_system_debug(f"Auditor Synthesizing: {question}")
        
        # Log input
        if interaction_id:
            log_agent_interaction(interaction_id, "Auditor", "Input", {
                "question": question,
                "context_provided": context
            }, None)

        full_prompt = TEXT_PROMPT.format(question=question, context=context)
        log_system_debug(f"Auditor Synthesizing: {full_prompt}")
        
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
        
        # Log output
        if interaction_id:
            log_agent_interaction(interaction_id, "Auditor", "Output", None, content)
        
        return content
        
    except Exception as e:
        log_system_error(f"AUDITOR EXCEPTION: {traceback.format_exc()}")
        return f"Error auditing result: {e}"
