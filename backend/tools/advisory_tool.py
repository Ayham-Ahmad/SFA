"""
Advisory Tool for LangChain Agent
=================================
Wraps the advisory functionality as a LangChain tool that the agent can call
when it needs to provide financial recommendations or insights.
"""
from langchain_core.tools import Tool
from backend.utils.llm_client import groq_client, get_model
from backend.core.logger import log_system_debug, log_system_error, log_agent_interaction

MODEL = get_model("default")

# Global state for logging and progress (set by LangChainAgent before running)
_current_interaction_id = None
_current_query_id = None

def set_advisory_interaction_id(interaction_id: str):
    """Set the interaction ID for logging purposes."""
    global _current_interaction_id
    _current_interaction_id = interaction_id

def set_advisory_query_id(query_id: str):
    """Set the query ID for progress updates."""
    global _current_query_id
    _current_query_id = query_id


def get_advisory_tool():
    """
    Create a LangChain tool for generating financial advisory insights.
    
    Returns:
        Tool: LangChain tool that generates advisory recommendations
    """
    
    def generate_advisory_insight(input_text: str) -> str:
        """
        Generate financial advisory insight based on question and data context.
        
        Args:
            input_text: Should contain the question and any relevant data context
        """
        global _current_interaction_id, _current_query_id
        
        # Update status for frontend
        if _current_query_id:
            from backend.pipeline.progress import set_query_progress
            set_query_progress(_current_query_id, "advisory", "💡 Generating advice...")
        
        log_system_debug(f"[AdvisoryTool] Generating insight for: {input_text[:100]}...")
        
        # Log tool call to chatbot_debug.json
        if _current_interaction_id:
            log_agent_interaction(_current_interaction_id, "AdvisoryTool", "Tool Call", input_text[:500], None)
        
        advisory_prompt = f"""You are a Smart Financial Advisor (SFA) providing professional financial insights.

CRITICAL PRINCIPLES:
1. NEVER imply direct control over market prices - prices are driven by supply/demand and market forces
2. Frame strategies as illustrative scenarios, NOT precise price targets
3. Acknowledge client context limitations
4. Provide clear, actionable guidance while acknowledging uncertainty

RESPONSE FORMAT:

**Context & Assumptions:**
- Asset type, timeframe, and key data points
- Note: "This analysis is suitable for investors with moderate risk tolerance"

**Assessment:**
What the data shows (trends, patterns, key observations)

**Strategy Options:**
Present 2-3 approaches with trade-offs:
- Conservative: [lower risk option]
- Moderate: [balanced approach]  
- Aggressive: [higher risk/reward option]

**Recommended Action:**
Clear next step based on the analysis

**Key Risks:**
Top 2-3 risks to monitor

User request and context:
{input_text}
"""
        
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": advisory_prompt}],
                model=MODEL,
                temperature=0.4,
                max_tokens=400  # Reduced to conserve API tokens
            )
            
            result = response.choices[0].message.content
            log_system_debug(f"[AdvisoryTool] Generated insight successfully")
            
            # Log result to chatbot_debug.json
            if _current_interaction_id:
                log_agent_interaction(_current_interaction_id, "AdvisoryTool", "Tool Result", "Advisory Response", result[:500])
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            log_system_error(f"[AdvisoryTool] Error: {error_msg}")
            
            # Log to debug but show user-friendly message
            if _current_interaction_id:
                log_agent_interaction(_current_interaction_id, "AdvisoryTool", "Error", "Advisory Failed", error_msg)
            
            # User-friendly messages
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                return "Advisory service is busy. Please try again shortly."
            else:
                return "Unable to generate advisory insight at this time."
    
    return Tool(
        name="advisory",
        func=generate_advisory_insight,
        description="MUST USE for strategy, advice, or recommendation questions. Provides professional financial insights. Input: the question plus any relevant data."
    )
