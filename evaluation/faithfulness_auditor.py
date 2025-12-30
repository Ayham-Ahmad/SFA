"""
Faithfulness Auditor Module
===========================

Custom Local Auditor that bypasses RAGAS's Groq limitations (n=1 error)
while maintaining hallucination detection for advisory queries.

This module performs zero-shot faithfulness scoring by comparing
the agent's response against the retrieved context using Groq/Llama.
"""

import re
import os
import logging
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FaithfulnessAuditor:
    """
    Performs faithfulness evaluation on advisory responses.
    
    Uses a direct Groq API call with a simple prompt to assess
    whether the response is grounded in the retrieved context.
    """
    
    def __init__(self, groq_client=None, model: str = "llama-3.3-70b-versatile"):
        """
        Initialize the auditor.
        
        Args:
            groq_client: Optional pre-configured Groq client. If None, creates one.
            model: The LLM model to use for auditing.
        """
        self.model = model
        
        if groq_client:
            self.client = groq_client
        else:
            # Create Groq client from environment
            try:
                from groq import Groq
                groq_key = os.getenv("GROQ_API_KEY")
                if groq_key:
                    self.client = Groq(api_key=groq_key)
                    logger.info("FaithfulnessAuditor initialized with Groq client")
                else:
                    self.client = None
                    logger.warning("GROQ_API_KEY not found - FaithfulnessAuditor disabled")
            except ImportError:
                self.client = None
                logger.warning("Groq package not installed - FaithfulnessAuditor disabled")
    
    def evaluate(self, query: str, response: str, retrieved_contexts: List[str]) -> Dict:
        """
        Performs a zero-shot faithfulness check optimized for Groq.
        
        Args:
            query: The user's original question
            response: The agent's generated response
            retrieved_contexts: List of context strings (SQL results, etc.)
        
        Returns:
            Dict with 'faithfulness' (0.0-1.0), 'answer_relevancy', and 'reason'
        """
        if not retrieved_contexts:
            return {
                "faithfulness": 0.0, 
                "answer_relevancy": 0.0,
                "reason": "No context provided"
            }
        
        if not self.client:
            return {
                "faithfulness": 0.5,  # Neutral when disabled
                "answer_relevancy": 0.5,
                "reason": "Auditor disabled (no API key)"
            }

        context_str = "\n".join(retrieved_contexts[:5])  # Limit context size
        
        # Simple, high-impact prompt for Groq (n=1 compatible)
        audit_prompt = f"""### ROLE
You are a Financial Auditor. Compare the PREMISE to the ANSWER.

### PREMISE (Retrieved Data)
{context_str}

### ANSWER (Agent Response)
{response}

### TASK
Identify if the ANSWER contains any numbers, dates, or claims NOT supported by the PREMISE.
Reply ONLY with a score between 0.0 (Hallucinated/Unsupported) and 1.0 (Completely Faithful).

Score:"""

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": audit_prompt}],
                temperature=0,
                max_tokens=10
            )
            
            raw_output = completion.choices[0].message.content
            
            # Extract number from response
            scores = re.findall(r"(\d+\.?\d*)", raw_output)
            if scores:
                faith_score = min(1.0, max(0.0, float(scores[0])))
            else:
                faith_score = 0.5  # Neutral if can't parse
            
            logger.info(f"Faithfulness Score: {faith_score:.2f}")
            
            return {
                "faithfulness": faith_score, 
                "answer_relevancy": 0.0,  # Computed separately via semantic similarity
                "reason": "Audit complete"
            }
            
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return {
                "faithfulness": 0.0,  # Fail closed
                "answer_relevancy": 0.0,
                "reason": str(e)
            }
    
    def is_available(self) -> bool:
        """Check if the auditor is properly configured."""
        return self.client is not None
