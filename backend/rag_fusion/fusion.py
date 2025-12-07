from typing import List
from backend.rag import rag_engine
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def generate_hyde_query(query: str) -> str:
    """
    Generate a Hypothetical Document Embedding (HyDE) query.
    """
    prompt = f"""
    Please write a short, hypothetical financial report snippet that answers the following question.
    Question: {query}
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"HyDE generation failed: {e}")
        return query

def generate_multi_queries(query: str) -> List[str]:
    """
    Generate multiple variations of the query for RAG Fusion.
    """
    prompt = f"""
    Generate 3 different search queries based on this user question to retrieve relevant financial data.
    User Question: {query}
    Output ONLY the 3 queries, one per line.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )
        content = response.choices[0].message.content
        queries = [q.strip() for q in content.split('\n') if q.strip()]
        return queries[:3]
    except Exception as e:
        print(f"Multi-query generation failed: {e}")
        return [query]

def rag_fusion_search(query: str, n_results: int = 5):
    """
    Perform RAG Fusion search:
    1. Generate multiple queries.
    2. Retrieve documents for each.
    3. Deduplicate and rank results (simplified Reciprocal Rank Fusion).
    """
    queries = generate_multi_queries(query)
    print(f"RAG Fusion Queries: {queries}")
    
    all_results = {}
    
    for q in queries:
        results = rag_engine.retrieve(q, n_results=n_results)
        for doc in results:
            # Use content as unique key for deduplication
            key = doc['content']
            if key not in all_results:
                all_results[key] = doc
    
    return list(all_results.values())
