from backend.agents.planner import plan_task
from backend.agents.worker import execute_step, set_interaction_id as set_worker_interaction_id
from backend.agents.auditor import audit_and_synthesize
from groq import Groq
import os
import traceback

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

import re

def extract_steps(plan: str):
    """
    Extract numbered or bullet steps regardless of formatting.
    """
    lines = re.split(r"\n|(?=\d+[\.\)]\s)", plan)
    steps = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # match leading number/bullet
        m = re.match(r"^\s*(\d+[\.\)]|-|\*)\s*(.*)", line)
        if m:
            steps.append(m.group(2).strip())
    
    return steps


def run_ramas_pipeline(question: str) -> str:
    """
    Orchestrates the RAMAS pipeline:
    1. Intent Classification: Skip pipeline for greetings.
    2. Planner: Decomposes question.
    3. Worker: Executes each step.
    4. Auditor: Synthesizes final answer.
    """

    print(f"\n--- Starting RAMAS Pipeline for: {question} ---")
    
    # 0. Check for Graph Authorization
    graph_allowed = False
    if question.startswith("[GRAPH_REQ]"):
        graph_allowed = True
        question = question.replace("[GRAPH_REQ]", "").strip()
        print(f"\nGraph Generation AUTHORIZED for: {question}")
    
    # Parse Input for Logging (Strip Context if present)
    log_input_query = question
    if "User Query:" in question:
        try:
            # Extract just the last part: "User Query: ..."
            parts = question.split("User Query:")
            if len(parts) > 1:
                log_input_query = parts[-1].strip()
        except:
            pass

    # 1. Intent Classification
    intent_prompt = f"""
    Classify the following user input into two categories:
    1. "CONVERSATIONAL": Greetings, small talk, questions about identity.
    2. "ANALYTICAL": Questions requiring data, numbers, financial info, companies, or database lookup.
    
    Input: {log_input_query}
    
    Return ONLY one word: "CONVERSATIONAL" or "ANALYTICAL".
    """
    try:
        classification = client.chat.completions.create(
            messages=[{"role": "user", "content": intent_prompt}],
            model=MODEL,
            temperature=0,
            max_tokens=10
        ).choices[0].message.content.strip().upper()
    except Exception as e:
        print(f"Intent Error: {e}")
        classification = "ANALYTICAL"

    if "CONVERSATIONAL" in classification:
        try:
            from backend.agent_debug_logger import log_agent_interaction
            import uuid
            interaction_id = str(uuid.uuid4())
            
            # Log only the cleaned user query
            log_agent_interaction(interaction_id, "User", "Input", log_input_query, None)
            
            chat_prompt = f"""
            You are a helpful Financial AI Assistant. 
            User says: "{log_input_query}"
            Reply consistently, professionally, and briefly.
            """
            
            reply = client.chat.completions.create(
                messages=[{"role": "user", "content": chat_prompt}],
                model=MODEL
            ).choices[0].message.content
            
            # Log the prompt template as "input" for the agent (better than full history), 
            # Or just log the answer. Let's log the cleaned query as input to keep it simple as requested.
            log_agent_interaction(interaction_id, "ConversationalAgent", "Output", log_input_query, reply)
            return reply
        except Exception as e:
            print(f"Conversational Error: {e}")
            return "Hello! How can I assist you today?"

    # 1. Plan
    try:
        from backend.d_log import dlog
        from backend.agent_debug_logger import log_agent_interaction
        import uuid
        
        # Generate a unique ID for this interaction flow
        interaction_id = str(uuid.uuid4())
        
        # Set interaction ID for worker's SQL logging
        set_worker_interaction_id(interaction_id)
        
        # Log User Query (Cleaned)
        log_agent_interaction(interaction_id, "User", "Input", log_input_query, None)
        
        # Use full context for Planning to maintain memory
        plan = plan_task(question, graph_allowed)
        dlog(f"Plan Generated:\n{plan}")
        log_agent_interaction(interaction_id, "Planner", "Output", log_input_query, plan)
        
        # 2. Work
        context = ""
        steps = extract_steps(plan)
        dlog(f"Extracted {len(steps)} steps: {steps}")  # DEBUG
        
        for step in steps:
            if step.strip():
                # Remove markdown bolding like "**SQL**:"
                clean_step = step.replace("**", "")
                dlog(f"Executing Step: {clean_step}")
                
                try:
                    result = execute_step(clean_step)
                    dlog(f"Step Result: {result[:200]}...") # Log summary
                except Exception as step_err:
                    result = f"Error executing step: {step_err}"
                    dlog(f"Step Error: {result}")
                
                context += f"\nStep: {step}\nResult: {result}\n"
                
                # Log Worker Step
                log_agent_interaction(interaction_id, "Worker", "Tool Call", clean_step, result)
        
        # 3. Audit
        dlog("Auditing and Synthesizing...")
        final_answer = audit_and_synthesize(question, context, graph_allowed, interaction_id=interaction_id)
        
        # NOTE: Auditor already logs its output internally
        
        # # 4. Safety Guard
        # from backend.security.safety import sanitize_content
        # safe_answer = sanitize_content(final_answer)
        
        dlog(f"Final Output: {final_answer[:100]}...")
        
        return final_answer

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        try:
            from backend.d_log import dlog
            dlog(f"Pipeline Error: {error_msg}")
        except:
            print(f"Pipeline Error: {error_msg}")
        return f"Error encountered: {str(e)}"
