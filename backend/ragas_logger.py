import json
import os
from datetime import datetime

RAGAS_LOG_FILE = "data/ragas_data.json"

def log_ragas_data(query: str, final_answer: str, rag_context: str):
    """
    Logs the query, final answer, and RAG context to a JSON file for RAGAS evaluation.
    
    Args:
        query: The user's original question.
        final_answer: The chatbot's final response.
        rag_context: The raw context retrieved from RAG (or SQL results treated as context).
    """
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(RAGAS_LOG_FILE), exist_ok=True)
    
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "final_answer": final_answer,
        "rag_context": rag_context
    }
    
    # Load existing data
    data = []
    if os.path.exists(RAGAS_LOG_FILE):
        try:
            with open(RAGAS_LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.strip():
                    data = json.loads(content)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {RAGAS_LOG_FILE}, starting new log.")
            
    # Append new entry
    data.append(entry)
    
    # Save back
    with open(RAGAS_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"Logged RAGAS data for query: '{query}'")
