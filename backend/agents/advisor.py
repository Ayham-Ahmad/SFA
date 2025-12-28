"""
Advisor Agent
=============
Generates advisory responses using user's connected database.
"""
from backend.utils.llm_client import groq_client, get_model
from backend.core.logger import log_system_debug, log_system_error

MODEL = get_model("default")


def generate_advisory(question: str, data_context: str = None, interaction_id: str = None, user=None) -> str:
    """
    Generates an advisory response.
    
    Args:
        question: User's advisory question
        data_context: Optional context from previous data retrieval
        interaction_id: Optional ID for logging
        user: Optional User model for user-specific data access
        
    Returns:
        Advisory recommendation text
    """
    # Use provided data context if available
    metrics_summary = data_context if data_context else "No specific data provided."
    
    # Build advisory prompt - PROFESSIONAL & CAUTIOUS
    advisory_prompt = f"""
You are a Smart Financial Advisor.

You provide cautious, high-level recommendations based on financial data.

RULES:
- NEVER give exact forecasts.
- Use directional language (increase / decrease / stable).
- Acknowledge uncertainty.
- Focus on sustainability and risk.
- Base analysis ONLY on the provided data.

RESPONSE STRUCTURE:
Assessment:
Recommendation:
Risks:
Next Steps:

User question: {question}

Data context:
{metrics_summary}
"""
    
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": advisory_prompt}],
            model=MODEL,
            temperature=0.4,
            max_tokens=600
        )
        
        recommendation = response.choices[0].message.content
        log_system_debug(f"[Advisor] Generated recommendation")
        return recommendation
        
    except Exception as e:
        log_system_error(f"[Advisor] Error: {e}")
        # Fallback to cautious response
        return """**Assessment:** Unable to fully analyze this question at the moment due to system limitations.

**Recommendation:** Before making this decision, please review your financial data and consult with your team.

**Risk Considerations:** Any financial decision should consider current market conditions and factors not captured in historical data.

**Suggested Next Steps:** Request a detailed analysis of relevant metrics for the most recent periods."""
