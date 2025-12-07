from backend.agents.planner import plan_task
from backend.agents.worker import execute_step
from backend.agents.auditor import audit_and_synthesize
from groq import Groq
import os
import traceback

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

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
        print(f"Graph Generation AUTHORIZED for: {question}")
    
    # 1. Intent Classification
    intent_prompt = f"""
    Classify the following user input into two categories:
    1. "CONVERSATIONAL": Greetings, small talk, questions about identity.
    2. "ANALYTICAL": Questions requiring data, numbers, financial info, companies, or database lookup.
    
    Input: {question}
    
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
        chat_prompt = f"""
        You are a helpful Financial AI Assistant. 
        User says: "{question}"
        Reply consistently, professionally, and briefly.
        """
        return client.chat.completions.create(
            messages=[{"role": "user", "content": chat_prompt}],
            model=MODEL
        ).choices[0].message.content

    # 1. Plan
    try:
        from backend.d_log import dlog
        plan = plan_task(question)
        dlog(f"Plan Generated:\n{plan}")
        
        # 2. Work
        context = ""
        steps = plan.split("\n")
        for step in steps:
            if step.strip() and (step[0].isdigit() or step.startswith("-")):
                # Remove markdown bolding like "**SQL**:"
                clean_step = step.replace("**", "")
                clean_step = clean_step.split(".", 1)[1].strip() if "." in clean_step else clean_step
                dlog(f"Executing Step: {clean_step}")
                result = execute_step(clean_step)
                dlog(f"Step Result: {result[:200]}...") # Log summary
                context += f"\nStep: {step}\nResult: {result}\n"
        
        # 3. Audit
        dlog("Auditing and Synthesizing...")
        final_answer = audit_and_synthesize(question, context, graph_allowed)
        
        # 4. Safety Guard
        from backend.security.safety import sanitize_content
        safe_answer = sanitize_content(final_answer)
        
        dlog(f"Final Output: {safe_answer[:100]}...")
        
        return safe_answer
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        dlog(f"Pipeline Error: {error_msg}")
        return f"Error encountered: {str(e)}"
