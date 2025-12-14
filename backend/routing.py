from backend.agents.planner import plan_task
from backend.agents.worker import execute_step, set_interaction_id as set_worker_interaction_id
from backend.agents.auditor import audit_and_synthesize
from groq import Groq
import os
import traceback

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

# ============================================
# TESTING FLAG imported from config
# ============================================
from backend.config import TESTING


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


def run_ramas_pipeline(question: str, query_id: str = None) -> str:
    """
    Orchestrates the RAMAS pipeline:
    1. Intent Classification: Skip pipeline for greetings.
    2. Planner: Decomposes question.
    3. Worker: Executes each step.
    4. Auditor: Synthesizes final answer.
    """
    
    # Import progress tracking (optional, won't crash if not available)
    try:
        from api.main import set_query_progress
        has_progress = True
    except:
        has_progress = False
        def set_query_progress(qid, agent, step): pass  # No-op fallback

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
    if TESTING:
        from backend.prompts import INTENT_PROMPT
        print(" ****** INTENT_PROMPT from prompts.py for testing")
        intent_prompt = INTENT_PROMPT.format(query=log_input_query)
        # Note: prompts.py INTENT_PROMPT uses {query} input, while inline uses {log_input_query}
    else:
        print(" ****** INTENT_PROMPT original")
        intent_prompt = f"""
I am currently working on classifying user inputs into specific categories to better understand their intent. The two categories are: "CONVERSATIONAL" for greetings, small talk, and identity questions, and "ANALYTICAL" for inquiries that require data, numbers, financial information, or database lookups. I find this task essential for streamlining responses based on user interaction.

Now, I want you to classify the following user input into one of the two categories. Please analyze the input: {log_input_query}. Your classification should reflect whether it falls under "CONVERSATIONAL" or "ANALYTICAL" based on the provided definitions.

The goal is to receive a clear classification of the user input, returning only one word: "CONVERSATIONAL" or "ANALYTICAL". This will help in tailoring the response appropriately according to the user's needs.
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
            
            if TESTING:
                from backend.prompts import CONVERSATIONAL_PROMPT
                print(" ****** CONVERSATIONAL_PROMPT from prompts.py for testing")
                chat_prompt = CONVERSATIONAL_PROMPT.format(query=log_input_query)
            else:
                print(" ****** CONVERSATIONAL_PROMPT original")
                chat_prompt = f"""
You are a professional Financial AI Assistant with extensive knowledge in personal finance, investments, and financial planning. Your primary goal is to provide accurate and insightful responses to users' financial queries while maintaining a tone that is both approachable and authoritative.

User says: "{log_input_query}"

Reply with a concise and well-structured response that addresses the user's question directly, providing relevant information and recommendations where applicable.

The response should be formatted in a clear and professional manner, starting with a brief acknowledgment of the user's query, followed by the main content of the answer, and concluding with any actionable suggestions or next steps.

Please keep in mind the following details:
- Ensure your responses are grounded in factual data and best practices in finance.
- Avoid using jargon without explanations to ensure clarity for all users.

Be cautious of providing overly complex answers that may confuse the user. Aim for brevity and clarity while ensuring that all relevant aspects of the query are addressed.
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

    # Step 2: Planner - Decompose the Question
    if has_progress and query_id:
        set_query_progress(query_id, "planner", "Breaking down question...")
    
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
        
        # Step 3: Worker - Execute Steps
        if has_progress and query_id:
            set_query_progress(query_id, "worker", "Executing queries...")
        
        context = ""
        steps = extract_steps(plan)
        dlog(f"Extracted {len(steps)} steps: {steps}")  # DEBUG
        
        # Testing Log Data Structure
        testing_log_entry = {
            "interaction_id": interaction_id,
            "timestamp": None, # Fill later if needed
            "user_query": log_input_query,
            "steps_context": [],
            "final_answer": None
        }
        
        for i, step in enumerate(steps):
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
                
                # Capture for testing_log
                if TESTING:
                    step_type = "UNKNOWN"
                    if "SQL" in clean_step.upper():
                        step_type = "SQL"
                    elif "RAG" in clean_step.upper():
                        step_type = "RAG"
                        
                    testing_log_entry["steps_context"].append({
                        "step_number": i + 1,
                        "type": step_type,
                        "tool_input": clean_step,
                        "retrieved_context": result
                    })
        
        # Step 4: Auditor - Synthesize Final Answer
        if has_progress and query_id:
            set_query_progress(query_id, "auditor", "Synthesizing answer...")
        
        final_answer = audit_and_synthesize(question, context, graph_allowed, interaction_id=interaction_id)
        
        # NOTE: Auditor already logs its output internally
        
        # # 4. Safety Guard
        # from backend.security.safety import sanitize_content
        # safe_answer = sanitize_content(final_answer)
        
        dlog(f"Final Output: {final_answer[:100]}...")
        
        # Save to testing.json if TESTING is enabled
        if TESTING:
            try:
                import json
                from datetime import datetime
                
                testing_log_entry["final_answer"] = final_answer
                testing_log_entry["timestamp"] = datetime.now().isoformat()
                
                testing_file_path = "testing.json"
                
                # Read existing data
                if os.path.exists(testing_file_path):
                    try:
                        with open(testing_file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
                else:
                    data = []
                
                # Append new entry
                data.append(testing_log_entry)
                
                # Write back
                with open(testing_file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                    
                print(f" ****** Logged interaction to {testing_file_path}")
                
            except Exception as e:
                print(f"Error writing to testing.json: {e}")
        
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
