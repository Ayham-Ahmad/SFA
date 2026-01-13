"""
Pipeline Router
===============
Orchestrates the LangChain agent pipeline for text and graph queries.
"""
from backend.utils.llm_client import groq_client, get_model, increment_api_counter
import traceback
import re
import uuid
from backend.core.logger import log_system_info, log_system_error, log_system_debug, log_agent_interaction
from backend.pipeline.progress import set_query_progress

MODEL = get_model("default")


# --- Progress Helper ---
def _update_progress(query_id: str, agent: str, step: str):
    """Update query progress for frontend display."""
    if query_id:
        set_query_progress(query_id, agent, step)


def classify_intent(question: str) -> list:
    """
    Classify the intent of the question.
    
    Returns:
        List of labels like ["DATA"], ["ADVISORY"], ["DATA", "ADVISORY"], 
        ["CONVERSATIONAL"], or ["BLOCKED"]
    """
    prompt = f"""Classify this query into one or more categories. Return ONLY the labels, comma-separated.

Categories:
- DATA: Needs database query (prices, revenue, metrics, numbers)
- ADVISORY: Asks for advice, recommendations, how to improve/raise/reduce something
- CONVERSATIONAL: Greetings, thanks, general chat
- BLOCKED: Off-topic, inappropriate, or non-financial

Query: "{question}"

Labels:"""
    
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL,
            temperature=0,
            max_tokens=30
        )
        # Track API call
        tokens = response.usage.total_tokens if response.usage else 0
        increment_api_counter(MODEL, tokens)
        
        result = response.choices[0].message.content.strip().upper()
        labels = [l.strip() for l in result.split(",")]
        valid_labels = ["DATA", "ADVISORY", "CONVERSATIONAL", "BLOCKED"]
        labels = [l for l in labels if l in valid_labels]
        return labels if labels else ["CONVERSATIONAL"]
    except Exception as e:
        log_system_error(f"Intent classification error: {e}")
        return ["DATA"]  # Default to data


def run_text_query_pipeline(question: str, query_id: str = None, user=None) -> str:
    """
    Run the unified LangChain agent pipeline.
    
    The agent has access to:
    - sql_query: Database queries
    - calculator: Mathematical calculations  
    - advisory: Financial recommendations
    
    Args:
        question: User's question
        query_id: Optional ID for progress tracking
        user: User model for database access
    """
    log_input_query = question[:500]
    log_system_info(f"Pipeline Start: {log_input_query}")
    
    # Classify intent (status already set by chat.py)
    labels = classify_intent(question)
    log_system_debug(f"Intent: {labels}")
    
    # Handle BLOCKED queries
    if "BLOCKED" in labels:
        return "I specialize in financial insights and can help with investment data, market analysis, and financial recommendations. Is there a financial topic I can assist you with?"
    
    # Handle pure CONVERSATIONAL queries
    if labels == ["CONVERSATIONAL"]:
        try:
            response = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a friendly financial assistant. Keep responses brief and helpful."},
                    {"role": "user", "content": question}
                ],
                model=MODEL,
                temperature=0.7,
                max_tokens=150
            )
            # Track API call
            tokens = response.usage.total_tokens if response.usage else 0
            increment_api_counter(MODEL, tokens)
            
            return response.choices[0].message.content
        except Exception as e:
            log_system_error(f"Conversational Error: {e}")
            return "Hello! How can I assist you today?"
    
    # Handle DATA, ADVISORY, or DATA+ADVISORY queries
    # All handled by unified LangChain agent with sql/calculator/advisory tools
    try:
        interaction_id = str(uuid.uuid4())
        log_agent_interaction(interaction_id, "User", "Input", log_input_query, None)
        
        # --- UNIFIED LANGCHAIN AGENT ---
        from backend.agents.langchain_agent import LangChainAgent
        
        _update_progress(query_id, "agent", "🤖 Agent is reasoning...")
        
        agent = LangChainAgent(user=user)
        # agent.run now returns a dict {"output": str, "steps": int}
        result = agent.run(question, interaction_id=interaction_id, query_id=query_id)
        
        # Log final output (extract text part)
        final_answer = result["output"] if isinstance(result, dict) else result
        log_system_debug(f"Final Output: {str(final_answer)[:100]}...")
        log_system_info(f"Pipeline Complete - Unified LangChain Agent")
        
        return result

    except Exception as e:
        error_msg = traceback.format_exc()
        log_system_error(f"Text Query Pipeline Failed: {str(e)}", error_msg)
        return {
            "output": f"I encountered an error processing your request: {str(e)}",
            "steps": 0
        }
