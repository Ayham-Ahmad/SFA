from backend.rag_fusion.fusion import rag_fusion_search
from backend.llm import run_chain_of_tables

WORKER_MODEL = "qwen/qwen3-32b"

def execute_step(step: str) -> str:
    """
    Executes a single step from the plan.
    """
    step = step.strip()
    
    if "RAG:" in step:
        query = step.split("RAG:", 1)[1].strip()
        print(f"Worker executing RAG: {query}")
        results = rag_fusion_search(query, n_results=3)
        # Summarize results
        return f"RAG Results for '{query}':\n" + "\n".join([f"- {r['content']}" for r in results])
    
    elif "SQL:" in step:
        query = step.split("SQL:", 1)[1].strip()
        print(f"Worker executing SQL: {query}")
        result = run_chain_of_tables(query, model=WORKER_MODEL)
        # Result is now raw data string, e.g. "Database Results: [...]"
        return f"SQL Execution Result for '{query}':\n{result}"
    
    else:
        return f"Unknown tool in step: {step}"
