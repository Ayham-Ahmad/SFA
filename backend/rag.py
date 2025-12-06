import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
import os

# Configuration
CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "data/vector_store")
COLLECTION_NAME = "financial_data"
MODEL_NAME = "all-MiniLM-L6-v2"

class RAGEngine:
    def __init__(self):
        print("Initializing RAG Engine...")
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.client.get_collection(name=COLLECTION_NAME)
        self.model = SentenceTransformer(MODEL_NAME)
        print("RAG Engine Ready.")

    def retrieve(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents for a given query.
        """
        try:
            query_embedding = self.model.encode([query]).tolist()
            
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results
            )
            
            formatted_results = []
            if results['documents']:
                for i, doc in enumerate(results['documents'][0]):
                    meta = results['metadatas'][0][i]
                    formatted_results.append({
                        "content": doc,
                        "metadata": meta,
                        "score": results['distances'][0][i] if 'distances' in results else None
                    })
            
            return formatted_results
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []

# Singleton instance
rag_engine = RAGEngine()
