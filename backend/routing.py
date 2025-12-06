from backend.agents.planner import plan_task
from backend.agents.worker import execute_step
from backend.agents.auditor import audit_and_synthesize
from groq import Groq
import os
import traceback

client = Groq(api_key=os.environ.get("OPENAI_API_KEY"))
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
    
    # 0. Intent Classification
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
        plan = plan_task(question)
        print(f"Plan:\n{plan}")
        
        # 2. Work
        context = ""
        steps = plan.split("\n")
        for step in steps:
            if step.strip() and (step[0].isdigit() or step.startswith("-")):
                # Remove markdown bolding like "**SQL**:"
                clean_step = step.replace("**", "")
                clean_step = clean_step.split(".", 1)[1].strip() if "." in clean_step else clean_step
                result = execute_step(clean_step)
                context += f"\nStep: {step}\nResult: {result}\n"
        
        # 3. Audit
        final_answer = audit_and_synthesize(question, context)
        print(f"Final Answer:\n{final_answer}")
        
        return final_answer
    except Exception as e:
        print(f"Pipeline Error: {traceback.format_exc()}")
        return f"Error encountered: {str(e)}"
