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
        
        advisory_prompt = f"""You are a Smart Financial Advisor (SFA) providing professional, data-driven financial insights.

MANDATORY RULES (follow strictly):
1. INTENT VALIDATION: Restate the user's goal. If the goal is flawed (e.g., "raise market price"), clarify what CAN vs CANNOT be controlled.
2. DATA GROUNDING: Every recommendation MUST reference actual data observations (time window, trends, volatility, patterns). No generic advice.
3. STRATEGY JUSTIFICATION: Explain WHY the chosen strategy fits the data, and why alternatives were not selected.
4. ACTIONABILITY: Provide concrete steps (what to do, how often, when to review/stop).
5. RISK & ASSUMPTIONS: Explicitly state key assumptions and primary risks.

RESPONSE FORMAT (use these exact section headers):

## 1. Objective Clarification
Restate the user's goal and clarify what can/cannot be directly influenced.
Example: "While closing prices cannot be directly controlled, investment outcomes can be influenced through timing, allocation, and risk management."

## 2. Data Summary
Summarize the data window and key observations from the provided data.
- Time period analyzed
- Key metrics observed (trend direction, volatility level, support/resistance, anomalies)
Example: "Analysis of the last 2 months shows moderate volatility (±5%) with no clear upward momentum."

## 3. Insight & Interpretation
Explain what the data implies for decision-making.
IMPORTANT: Include an explicit scope statement like: "This interpretation is based on short-term price action and volatility. Volume trends and fundamental indicators are not incorporated in this analysis."
Example: "The sideways pattern with frequent reversals suggests elevated timing risk for lump-sum entry."

## 4. Recommended Strategy
State ONE clear recommendation and justify it based on the data.
Add: "The advisory therefore focuses on investment positioning rather than price manipulation."
Example: "Dollar-cost averaging is recommended to mitigate entry timing risk under uncertain short-term conditions."

## 5. Execution Guidance
Provide concrete, actionable steps with FLEXIBILITY:
- What to do
- Frequency/timeline (offer options: "weekly or monthly tranches, depending on operational constraints and transaction costs")
- Trigger for reassessment
Example: "Allocate in equal weekly or bi-weekly tranches over 6 months. Review if volatility exceeds 10% or a breakout occurs."

## 6. Risks, Assumptions & Downside Protection
List 2-3 key assumptions and risks.
MUST INCLUDE explicit downside protection/exit rule.
Example:
- Assumption: Market remains range-bound
- Risk: Sudden breakout or macroeconomic shock may reduce effectiveness
- Downside Protection: "If price consistently breaks below the identified support level with increasing volatility, pause capital deployment pending reassessment."

## 7. Confidence Note
A brief reliability statement.
Example: "This advisory is based on limited historical data and should be used as decision support, not a standalone directive."

---
User request and data context:
{input_text}
"""
        
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": advisory_prompt}],
                model=MODEL,
                temperature=0.4,
                max_tokens=700  # Increased for structured 7-section advisory template
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
