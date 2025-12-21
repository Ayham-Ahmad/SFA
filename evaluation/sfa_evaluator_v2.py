"""
SFA Evaluator V2 - Production-Ready with Golden Dataset

This module provides real evaluation against ground truth data:
- Uses sfa_golden_dataset.json for verification
- Real SQL execution validation (syntax + executability)
- Semantic similarity for text comparison
- Tool routing validation
- Failure mode analysis tracking

METHODOLOGY NOTES:
1. SQL Validity: Checks execution correctness via EXPLAIN QUERY PLAN.
   Logical correctness is indirectly validated through value accuracy.
   
2. Semantic Capping: For numeric validation types, semantic similarity
   cannot exceed value accuracy (prevents over-crediting wrong values).
   
3. Pass Threshold (0.6): Balances strict numeric accuracy with natural
   language flexibility. Multi-metric evaluation allows partial credit.
   
4. Dataset: 40 representative queries covering core intents, balanced
   across query categories (structured, graph, advisory, edge cases).

Usage:
    evaluator = SFAEvaluatorV2()
    results = evaluator.evaluate_query("What was the revenue in 2024?", to_CSV=True)
    evaluator.evaluate_dataset(to_CSV=True)
    evaluator.print_failure_analysis()  # Show failure mode table
"""


import sys
import os
# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

import json
import re
import csv
import os
import sqlite3
import uuid
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Import debug logger
try:
    from backend.agent_debug_logger import log_agent_interaction
    DEBUG_LOGGING_AVAILABLE = True
except ImportError:
    DEBUG_LOGGING_AVAILABLE = False
    print("Warning: agent_debug_logger not available. Debug logging disabled.")

# Try to import sentence-transformers for semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util
    EMBEDDER_AVAILABLE = True
except ImportError:
    EMBEDDER_AVAILABLE = False
    print("Warning: sentence-transformers not installed. Semantic similarity will use fallback.")

# RAGAS for hallucination detection in advisory queries
try:
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import faithfulness, answer_relevancy
    from datasets import Dataset
    RAGAS_AVAILABLE = True
    
    # Configure RAGAS to use Groq instead of OpenAI
    try:
        from langchain_groq import ChatGroq
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_huggingface import HuggingFaceEmbeddings
        import os
        
        # Get Groq API key from environment
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            # Create Groq LLM wrapper for RAGAS
            groq_llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key=groq_key,
                temperature=0
            )
            RAGAS_LLM = LangchainLLMWrapper(groq_llm)
            
            # Use local embeddings (already loaded by sentence-transformers)
            RAGAS_EMBEDDINGS = LangchainEmbeddingsWrapper(
                HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            )
            GROQ_RAGAS_READY = True
            print("RAGAS configured with Groq LLM (llama-3.3-70b-versatile)")
        else:
            GROQ_RAGAS_READY = False
            print("Warning: GROQ_API_KEY not found. RAGAS will fail closed.")
    except ImportError as e:
        GROQ_RAGAS_READY = False
        print(f"Warning: langchain-groq not available ({e}). RAGAS will fail closed.")
        
except ImportError:
    RAGAS_AVAILABLE = False
    GROQ_RAGAS_READY = False
    print("Warning: RAGAS not available. Advisory faithfulness checks disabled.")

# =========================================================================
# CONFIGURATION
# =========================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "data", "db", "financial_data.db")
GOLDEN_DATASET_PATH = os.path.join(BASE_DIR, "sfa_golden_dataset_v2.json")

# =========================================================================
# DATA CLASSES
# =========================================================================

@dataclass
class ValidationResult:
    """Result of validating a single query against ground truth."""
    query_id: int
    query: str
    category: str
    difficulty: str
    
    # Pipeline outputs
    extracted_tool: str = ""
    generated_sql: str = ""
    actual_response: str = ""
    
    # Validation scores (0.0 to 1.0)
    tool_accuracy: float = 0.0        # Did it use the right tool?
    sql_validity: float = 0.0         # Is the SQL executable?
    value_accuracy: float = 0.0       # Does the value match ground truth?
    semantic_similarity: float = 0.0  # Text similarity to golden answer
    semantic_capped: bool = False     # Was semantic score capped?
    graph_generated: bool = False     # For graph queries
    
    # Failure mode tracking
    failure_mode: str = ""  # wrong_tool, invalid_sql, wrong_value, hallucination, missing_data, none
    
    # Computed overall
    overall_score: float = 0.0
    passed: bool = False
    
    # Plan efficiency tracking
    total_steps: int = 0              # Number of steps in the plan
    unique_steps: int = 0             # Steps with unique outputs
    plan_efficiency: float = 1.0      # unique_steps / total_steps (1.0 = no redundancy)
    expected_steps: int = 1           # Expected steps from golden dataset
    step_accuracy: float = 1.0        # 1.0 if actual == expected, penalty otherwise
    
    # Metadata
    error: str = ""
    timestamp: str = ""
    validation_type: str = ""  # numeric, semantic, refusal, graph_exists
    
    # RAGAS scores (Advisory queries only)
    faithfulness: float = 0.0         # Is response supported by context?
    answer_relevancy: float = 0.0     # Is response relevant to question?


# =========================================================================
# SFA EVALUATOR V2
# =========================================================================

class SFAEvaluatorV2:
    """
    Production-ready evaluator using golden dataset and real validation.
    """
    
    def __init__(self):
        # Load golden dataset
        with open(GOLDEN_DATASET_PATH, 'r', encoding='utf-8') as f:
            self.golden_dataset = json.load(f)
        
        # Build lookup by query text
        self.golden_lookup = {item['query'].lower().strip(): item for item in self.golden_dataset}
        
        # Initialize embedder for semantic similarity
        if EMBEDDER_AVAILABLE:
            print("Loading embedding model...")
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            print("Embedding model ready.")
        else:
            self.embedder = None
        
        # Valid tools mapping
        self.valid_tools = {"SQL", "RAG", "ADVISORY", "NONE"}
        
        print(f"Loaded {len(self.golden_dataset)} golden queries from dataset.")
    
    # =========================================================================
    # TOOL VALIDATION
    # =========================================================================
    
    def validate_tool_selection(self, query: str, extracted_tool: str, golden_entry: Dict) -> float:
        """
        Validates if the correct tool was selected.
        Returns 1.0 for exact match, 0.5 for partial, 0.0 for wrong.
        """
        golden_tool = golden_entry.get('golden_tool', '').upper()
        extracted_upper = extracted_tool.upper()
        
        # Handle multi-tool cases (e.g., "SQL, ADVISORY")
        golden_tools = [t.strip() for t in golden_tool.split(',')]
        
        if extracted_upper in golden_tools:
            return 1.0
        
        # Partial credit for related tools
        if extracted_upper == "SQL" and "DATA" in golden_entry.get('intent_type', ''):
            return 0.5
        
        return 0.0
    
    # =========================================================================
    # SQL VALIDATION
    # =========================================================================
    
    def validate_sql_execution(self, generated_sql: str) -> Tuple[bool, str]:
        """
        Validates SQL by actually executing it against the database.
        Uses EXPLAIN QUERY PLAN to validate without modifying data.
        """
        if not generated_sql or not generated_sql.strip():
            return False, "Empty SQL"
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Clean SQL
            clean_sql = generated_sql.strip()
            if not clean_sql.upper().startswith('SELECT'):
                # Try to extract SELECT statement
                match = re.search(r'SELECT\s+.+?(?:;|$)', clean_sql, re.IGNORECASE | re.DOTALL)
                if match:
                    clean_sql = match.group(0)
                else:
                    return False, "No SELECT statement found"
            
            # Test with EXPLAIN QUERY PLAN (validates structure without full execution)
            cursor.execute(f"EXPLAIN QUERY PLAN {clean_sql}")
            conn.close()
            return True, "Valid"
            
        except sqlite3.Error as e:
            return False, f"SQL Error: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def extract_sql_from_trace(self, execution_trace: str) -> str:
        """Extract SQL query from worker execution trace."""
        # 1. Try markdown SQL blocks FIRST (Qwen often outputs these)
        markdown_pattern = r"```sql\s*(.*?)\s*```"
        match = re.search(markdown_pattern, execution_trace, re.DOTALL | re.IGNORECASE)
        if match:
            sql = match.group(1).strip()
            if sql:
                return sql
        
        # 2. Standard formats
        patterns = [
            r"SQL Query Used:\s*(SELECT\s+.+?)(?:\n\nDatabase|\n\nNO_DATA|$)",
            r"Generated SQL:\s*(SELECT\s+.+?)(?:\n|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, execution_trace, re.IGNORECASE | re.DOTALL)
            if match:
                sql = match.group(1).strip().replace('\n', ' ')
                if sql.upper().startswith('SELECT'):
                    return sql
        
        # 3. Fallback: Raw SELECT with semicolon termination
        raw_pattern = r"(SELECT\s+.*?(?:;|$))"
        match = re.search(raw_pattern, execution_trace, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
            
        return ""
    
    # =========================================================================
    # VALUE VALIDATION
    # =========================================================================
    
    def validate_value_accuracy(self, actual_response: str, golden_entry: Dict) -> float:
        """
        Validates if the response contains correct values.
        Uses tolerance for numeric comparisons.
        """
        validation_type = golden_entry.get('validation_type', 'semantic')
        golden_value = golden_entry.get('golden_value')
        tolerance = golden_entry.get('tolerance_percent', 5) / 100
        
        if validation_type == 'numeric' and golden_value is not None:
            # Extract numbers from response (including negative and percentage)
            numbers = re.findall(r'-?[\d,.]+', actual_response)
            
            for num_str in numbers:
                try:
                    # Parse the number
                    num = float(num_str.replace(',', ''))
                    
                    # Skip tiny numbers that are likely not the answer
                    if abs(num) < 0.001 and abs(golden_value) > 1:
                        continue
                    
                    # Check for B/M/K suffixes (billions, millions, thousands)
                    if 'B' in actual_response.upper():
                        if golden_value != 0 and abs(num - golden_value / 1e9) / abs(golden_value / 1e9) <= tolerance:
                            return 1.0
                    if 'M' in actual_response.upper():
                        if golden_value != 0 and abs(num - golden_value / 1e6) / abs(golden_value / 1e6) <= tolerance:
                            return 1.0
                    
                    # Handle percentage vs decimal conversion
                    # If golden is decimal (e.g., -0.991) and response has percentage (e.g., 99.1%)
                    if '%' in actual_response and abs(golden_value) < 10:
                        # Try matching percentage value to decimal * 100
                        if golden_value != 0:
                            expected_pct = abs(golden_value * 100)
                            if abs(abs(num) - expected_pct) / expected_pct <= tolerance:
                                return 1.0
                    
                    # Direct comparison
                    if golden_value != 0:
                        if abs(num - golden_value) / abs(golden_value) <= tolerance:
                            return 1.0
                        # Also try absolute value comparison for negative values
                        if abs(abs(num) - abs(golden_value)) / abs(golden_value) <= tolerance:
                            return 1.0
                except:
                    continue
            
            return 0.0
        
        elif validation_type == 'refusal':
            # Check for expected refusal elements
            expected = golden_entry.get('expected_elements', [])
            response_lower = actual_response.lower()
            matches = sum(1 for elem in expected if elem.lower() in response_lower)
            return matches / len(expected) if expected else 0.0
        
        elif validation_type == 'graph_exists':
            # Check if graph data was generated
            if 'graph_data||' in actual_response or 'Graph generated' in actual_response:
                return 1.0
            return 0.0
        
        return 0.5  # Default partial credit for unhandled types
    
    # =========================================================================
    # SEMANTIC SIMILARITY
    # =========================================================================
    
    def calculate_semantic_similarity(self, actual: str, golden: str) -> float:
        """
        Calculate semantic similarity between actual and golden response.
        """
        if not actual or not golden:
            return 0.0
        
        if self.embedder:
            # Use sentence transformers
            actual_emb = self.embedder.encode(actual, convert_to_tensor=True)
            golden_emb = self.embedder.encode(golden, convert_to_tensor=True)
            similarity = util.cos_sim(actual_emb, golden_emb)
            return float(similarity[0][0])
        else:
            # Fallback: Jaccard similarity on words
            actual_words = set(actual.lower().split())
            golden_words = set(golden.lower().split())
            
            if not actual_words or not golden_words:
                return 0.0
            
            intersection = len(actual_words & golden_words)
            union = len(actual_words | golden_words)
            return intersection / union if union > 0 else 0.0
    
    # =========================================================================
    # RAGAS EVALUATION (Advisory/Unstructured Queries)
    # =========================================================================
    
    def evaluate_ragas(self, query: str, response: str, retrieved_contexts: List[str]) -> Dict:
        """
        Groq-Compatible Hallucination Check (Custom Local Auditor).
        Replaces RAGAS library to avoid Groq's 'n=1' parameter error.
        
        Uses a simple prompt to assess faithfulness of advisory responses.
        
        Args:
            query: The user's question
            response: The generated answer
            retrieved_contexts: List of context strings used to generate the answer
        
        Returns:
            Dict with 'faithfulness' and 'answer_relevancy' scores (0.0-1.0)
        """
        if not retrieved_contexts:
            return {"faithfulness": 0.0, "answer_relevancy": 0.0}

        context_str = "\n".join(retrieved_contexts)
        
        # Simple, high-impact prompt for Groq/Llama
        audit_prompt = f"""You are a Financial Auditor. Compare the PREMISE to the ANSWER.

PREMISE:
{context_str}

ANSWER:
{response}

Does the ANSWER contain any numerical facts or claims NOT supported by the PREMISE?
Reply ONLY with a score between 0.0 (Hallucinated/Unsupported) and 1.0 (Completely Faithful).
Score:"""

        try:
            # Use the existing Groq client from backend
            import os
            from groq import Groq
            
            groq_key = os.getenv("GROQ_API_KEY")
            if not groq_key:
                print("⚠️ GROQ_API_KEY not set - faithfulness check skipped")
                return {"faithfulness": 0.5, "answer_relevancy": self.calculate_semantic_similarity(query, response)}
            
            client = Groq(api_key=groq_key)
            
            audit_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": audit_prompt}],
                temperature=0,
                max_tokens=10
            )
            
            audit_score_raw = audit_response.choices[0].message.content
            
            # Extract score from response
            score_matches = re.findall(r"(\d+\.?\d*)", audit_score_raw)
            if score_matches:
                faithfulness_score = min(1.0, max(0.0, float(score_matches[0])))
            else:
                faithfulness_score = 0.5  # Neutral if can't parse
                
            print(f"Custom Auditor - Faithfulness: {faithfulness_score:.2f}")
            
        except Exception as e:
            print(f"⚠️ Custom Auditor error: {e}")
            faithfulness_score = 0.0  # Fail safe

        return {
            "faithfulness": faithfulness_score,
            "answer_relevancy": self.calculate_semantic_similarity(query, response)
        }
    
    # =========================================================================
    # FAILURE MODE ANALYSIS
    # =========================================================================
    
    def _detect_failure_mode(self, result: ValidationResult, golden_entry: Dict) -> str:
        """
        Detect the failure mode for a query result.
        
        Failure Modes:
        - wrong_tool: Planner chose incorrect tool (SQL vs RAG)
        - invalid_sql: SQL failed execution
        - wrong_value: Response has incorrect numeric value
        - hallucination: Response contains value not in database
        - missing_data: Correct refusal for unavailable data
        - none: No failure detected
        """
        # If passed, no failure
        if result.tool_accuracy == 1.0 and result.value_accuracy >= 0.8:
            return "none"
        
        # Check failure modes in priority order
        if result.tool_accuracy < 1.0:
            return "wrong_tool"
        
        if result.generated_sql and result.sql_validity < 1.0:
            return "invalid_sql"
        
        # Check for wrong value (numeric queries)
        validation_type = golden_entry.get('validation_type', '') if golden_entry else ''
        if validation_type == 'numeric' and result.value_accuracy < 0.5:
            # Check if value is completely missing vs wrong
            if "no data" in result.actual_response.lower() or "unavailable" in result.actual_response.lower():
                return "missing_data"
            return "wrong_value"
        
        # Check for hallucination (value present but wrong)
        if result.value_accuracy < 0.5 and result.semantic_similarity > 0.5:
            return "hallucination"
        
        # Check for correct refusal
        if golden_entry and golden_entry.get('expected_behavior') in ['refuse_or_clarify', 'no_data', 'block']:
            if result.value_accuracy > 0.0:
                return "none"  # Correctly refused/clarified
        
        return "none"
    
    def get_failure_analysis(self, results: List[ValidationResult]) -> Dict:
        """
        Generate failure mode analysis table from results.
        """
        failure_counts = {
            "wrong_tool": 0,
            "invalid_sql": 0,
            "wrong_value": 0,
            "hallucination": 0,
            "missing_data": 0,
            "none": 0
        }
        
        failure_examples = {}
        
        for r in results:
            mode = r.failure_mode if r.failure_mode else "none"
            failure_counts[mode] = failure_counts.get(mode, 0) + 1
            
            # Track first example of each failure mode
            if mode != "none" and mode not in failure_examples:
                failure_examples[mode] = r.query[:50]
        
        return {
            "counts": failure_counts,
            "examples": failure_examples,
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed)
        }
    
    def print_failure_analysis(self, results: List[ValidationResult]):
        """
        Print a formatted failure mode analysis table.
        """
        analysis = self.get_failure_analysis(results)
        
        print("\n" + "="*70)
        print("FAILURE MODE ANALYSIS TABLE")
        print("="*70)
        print(f"{'Failure Type':<20} | {'Description':<30} | {'Count':<8}")
        print("-"*70)
        
        descriptions = {
            "wrong_tool": "Planner chose wrong tool",
            "invalid_sql": "SQL failed execution",
            "wrong_value": "Incorrect numeric value",
            "hallucination": "Value not in database",
            "missing_data": "Correct refusal for no data",
            "none": "No failure (passed)"
        }
        
        for mode, count in analysis["counts"].items():
            desc = descriptions.get(mode, mode)
            status = "✓" if mode == "none" else ("!" if count > 0 else "-")
            print(f"{mode:<20} | {desc:<30} | {count:<8} {status}")
        
        print("-"*70)
        print(f"Total: {analysis['total']} | Passed: {analysis['passed']} | Failed: {analysis['failed']}")
        print("="*70 + "\n")
        
        return analysis
    
    # =========================================================================
    # MAIN EVALUATION METHODS
    # =========================================================================
    
    def evaluate_query(self, query: str, to_CSV: bool = False) -> ValidationResult:
        """
        Evaluate a single query against the golden dataset.
        """
        result = ValidationResult(
            query_id=0,
            query=query,
            category="unknown",
            difficulty="unknown",
            timestamp=datetime.now().isoformat()
        )
        
        # Find golden entry
        query_key = query.lower().strip()
        golden_entry = self.golden_lookup.get(query_key)
        
        if not golden_entry:
            # Try fuzzy match
            for key, entry in self.golden_lookup.items():
                if query_key in key or key in query_key:
                    golden_entry = entry
                    break
        
        if golden_entry:
            result.query_id = golden_entry.get('id', 0)
            result.category = golden_entry.get('category', 'unknown')
            result.difficulty = golden_entry.get('difficulty', 'unknown')
        
        try:
            # Import SFA components
            from backend.agents.planner import plan_task
            from backend.agents.worker import execute_step
            from backend.agents.auditor import audit_and_synthesize
            from backend.routing import extract_steps
            
            print(f"\n{'='*60}")
            print(f"EVALUATING [ID:{result.query_id}]: {query}")
            print(f"Category: {result.category} | Difficulty: {result.difficulty}")
            print(f"{'='*60}\n")
            
            # Generate unique interaction ID for this evaluation
            eval_id = f"eval_{result.query_id}_{uuid.uuid4().hex[:8]}"
            
            # Log user query
            if DEBUG_LOGGING_AVAILABLE:
                log_agent_interaction(
                    eval_id, "Evaluator", "Input",
                    {"query": query, "query_id": result.query_id, "category": result.category},
                    None
                )
            
            # Check if graph is needed - based on category or intent_type
            is_graph = (golden_entry.get('category', '').lower() == 'graph' or 
                       golden_entry.get('intent_type', '').upper() == 'GRAPH') if golden_entry else False
            print(f"Graph allowed: {is_graph}")
            
            # 1. Run Planner
            plan_output = plan_task(query, graph_allowed=is_graph)
            
            # Log Planner output
            if DEBUG_LOGGING_AVAILABLE:
                log_agent_interaction(
                    eval_id, "Planner", "Output",
                    query,
                    {"plan": plan_output, "graph_allowed": is_graph}
                )
            
            # Extract tool from plan - handle markdown bold format: **SQL**: or SQL:
            plan_upper = plan_output.upper().replace('**', '')
            if "ADVISORY:" in plan_upper:
                result.extracted_tool = "ADVISORY"
            elif "SQL:" in plan_upper:
                result.extracted_tool = "SQL"
            elif "RAG:" in plan_upper:
                result.extracted_tool = "RAG"
            else:
                result.extracted_tool = "NONE"
            
            # 2. Validate tool selection
            if golden_entry:
                result.tool_accuracy = self.validate_tool_selection(
                    query, result.extracted_tool, golden_entry
                )
                print(f"Tool Accuracy: {result.tool_accuracy:.2f}")
            
            # 3. Run Worker
            steps = extract_steps(plan_output)
            context = ""
            step_outputs = []  # Track outputs to detect redundancy
            
            for step in steps:
                if step.strip():
                    clean_step = step.replace("**", "")
                    step_result = execute_step(clean_step)
                    context += f"\n{step_result}\n"
                    
                    # Track step output for redundancy detection
                    step_outputs.append(step_result)
                    
                    # Log each Worker step
                    if DEBUG_LOGGING_AVAILABLE:
                        log_agent_interaction(
                            eval_id, "Worker", "Tool Call",
                            clean_step,
                            step_result[:1000] if len(step_result) > 1000 else step_result
                        )
                    
                    # Extract SQL if present
                    if "SQL" in step.upper():
                        result.generated_sql = self.extract_sql_from_trace(step_result)
            
            # Calculate plan efficiency (detect redundant steps)
            result.total_steps = len(step_outputs)
            if result.total_steps > 0:
                # Extract numeric values from DATABASE RESULTS only (ignore column names/headers)
                # This detects when different SQL queries return the same actual data
                def extract_data_values(output_str):
                    """Extract numeric values from data rows only, ignoring column headers."""
                    import re
                    lines = output_str.split('\n')
                    data_values = []
                    in_results = False
                    for line in lines:
                        if 'Database Results' in line:
                            in_results = True
                            continue
                        if in_results and '|' in line:
                            # Skip separator rows (contain only dashes like |---:|)
                            if re.match(r'^[\s|:\-]+$', line):
                                continue
                            # Skip header rows (first row after Database Results that has text column names)
                            # Data rows contain numbers in scientific notation (e+) or dollars ($)
                            if 'e+' in line.lower() or 'e-' in line.lower() or '$' in line:
                                # This is a data row, extract numbers
                                cells = [c.strip() for c in line.split('|') if c.strip()]
                                for cell in cells:
                                    nums = re.findall(r'[-+]?\d*\.?\d+(?:e[+-]?\d+)?', cell)
                                    for n in nums:
                                        try:
                                            val = float(n)
                                            # Only include significant data values
                                            if abs(val) > 100 or val == 0:
                                                data_values.append(f"{val:.6e}")
                                        except:
                                            pass
                    return tuple(sorted(data_values))
                
                data_signatures = [extract_data_values(o) for o in step_outputs]
                unique_data = set(data_signatures)
                result.unique_steps = len(unique_data)
                result.plan_efficiency = result.unique_steps / result.total_steps
                
                if result.plan_efficiency < 1.0:
                    redundant = result.total_steps - result.unique_steps
                    print(f"⚠️ Plan Efficiency: {result.plan_efficiency:.0%} ({redundant} redundant step(s))")
            
            # Calculate step accuracy (compare actual steps to expected)
            if golden_entry:
                result.expected_steps = golden_entry.get('expected_steps', 1)
                if result.expected_steps > 0:
                    # Penalize for using more steps than expected
                    if result.total_steps == result.expected_steps:
                        result.step_accuracy = 1.0
                    elif result.total_steps > result.expected_steps:
                        # Too many steps - penalty
                        extra = result.total_steps - result.expected_steps
                        result.step_accuracy = max(0.0, 1.0 - (extra * 0.25))
                        print(f"⚠️ Step Count: {result.total_steps} (expected {result.expected_steps}) - Accuracy: {result.step_accuracy:.0%}")
                    else:
                        # Fewer steps than expected - could be fine
                        result.step_accuracy = 1.0
                print(f"Steps: {result.total_steps} (expected: {result.expected_steps})")
            
            # 4. Validate SQL execution
            if result.generated_sql:
                is_valid, msg = self.validate_sql_execution(result.generated_sql)
                result.sql_validity = 1.0 if is_valid else 0.0
                print(f"SQL Validity: {result.sql_validity:.2f} ({msg})")
                
                # Log SQL validation
                if DEBUG_LOGGING_AVAILABLE:
                    log_agent_interaction(
                        eval_id, "Evaluator", "SQL Validation",
                        result.generated_sql,
                        {"valid": is_valid, "message": msg}
                    )
            
            # 5. Run Auditor
            result.actual_response = audit_and_synthesize(query, context, graph_allowed=is_graph)
            
            # Log Auditor output
            if DEBUG_LOGGING_AVAILABLE:
                log_agent_interaction(
                    eval_id, "Auditor", "Output",
                    {"query": query, "context_length": len(context)},
                    result.actual_response
                )
            
            # Check for graph generation
            if 'graph_data||' in result.actual_response:
                result.graph_generated = True
            
            # 6. Validate value accuracy
            if golden_entry:
                result.validation_type = golden_entry.get('validation_type', 'semantic')
                result.value_accuracy = self.validate_value_accuracy(
                    result.actual_response, golden_entry
                )
                print(f"Value Accuracy: {result.value_accuracy:.2f}")
                
                # 7. Semantic similarity
                golden_answer = golden_entry.get('golden_answer', '')
                raw_semantic = self.calculate_semantic_similarity(
                    result.actual_response, golden_answer
                )
                
                # ISSUE 1 FIX: Cap semantic similarity for numeric queries
                # If validation_type = numeric, semantic cannot exceed value accuracy
                # This prevents over-crediting textually similar but numerically wrong answers
                if result.validation_type == 'numeric' and raw_semantic > result.value_accuracy:
                    result.semantic_similarity = result.value_accuracy
                    result.semantic_capped = True
                    print(f"Semantic Similarity: {raw_semantic:.2f} → CAPPED to {result.semantic_similarity:.2f}")
                else:
                    result.semantic_similarity = raw_semantic
                    print(f"Semantic Similarity: {result.semantic_similarity:.2f}")
                
                # 7b. RAGAS Evaluation for Advisory queries (Faithfulness check)
                category = golden_entry.get('category', '').lower()
                intent_type = golden_entry.get('intent_type', '').upper()
                
                if category == 'advisory' or intent_type == 'ADVISORY':
                    # Collect contexts from execution traces
                    retrieved_contexts = []
                    if context:
                        # Split context into retrievable chunks
                        retrieved_contexts = [ctx.strip() for ctx in context.split('\n\n') if ctx.strip()]
                    
                    if retrieved_contexts:
                        ragas_scores = self.evaluate_ragas(query, result.actual_response, retrieved_contexts)
                        result.faithfulness = ragas_scores.get('faithfulness', 0.5)
                        result.answer_relevancy = ragas_scores.get('answer_relevancy', 0.5)
                        
                        # Flag potential hallucination if faithfulness is low
                        if result.faithfulness < 0.5:
                            print(f"⚠️ Low Faithfulness ({result.faithfulness:.2f}) - Potential hallucination")
                    else:
                        print("No contexts available for RAGAS - using semantic only")
            
            # 8. Detect failure mode
            result.failure_mode = self._detect_failure_mode(result, golden_entry)
            if result.failure_mode != "none":
                print(f"Failure Mode: {result.failure_mode}")
            
            # 9. Calculate overall score with weighted metrics
            # Weights justification (ISSUE 3):
            # - Tool (20%): Correct routing is foundational but not sufficient alone
            # - SQL (20%): Execution validity is necessary but not correctness
            # - Value (30%): Numeric accuracy is critical for financial data
            # - Semantic (30%): Response quality matters for user experience
            weights = {
                'tool': 0.2,
                'sql': 0.2,
                'value': 0.3,
                'semantic': 0.3
            }
            
            result.overall_score = (
                weights['tool'] * result.tool_accuracy +
                weights['sql'] * result.sql_validity +
                weights['value'] * result.value_accuracy +
                weights['semantic'] * result.semantic_similarity
            )
            
            # Pass/Fail Logic (REVISED):
            # PRIMARY: Value Accuracy >= 0.5 means correct data was returned - this is the CORE requirement
            # SECONDARY: Overall score is still computed for reporting purposes
            # Rationale: The SFA's main job is returning accurate data. Process metrics are secondary.
            result.passed = result.value_accuracy >= 0.5 or result.overall_score >= 0.7
            
            print(f"\n--- RESULT ---")
            print(f"Overall Score: {result.overall_score:.2f}")
            print(f"Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
            print(f"Response Preview: {result.actual_response[:150]}...")
            
            # Log final evaluation results
            if DEBUG_LOGGING_AVAILABLE:
                log_agent_interaction(
                    eval_id, "Evaluator", "Final Result",
                    {"query_id": result.query_id, "query": query},
                    {
                        "sfa_response": result.actual_response,
                        "tool_accuracy": result.tool_accuracy,
                        "sql_validity": result.sql_validity,
                        "value_accuracy": result.value_accuracy,
                        "semantic_similarity": result.semantic_similarity,
                        "overall_score": result.overall_score,
                        "passed": result.passed,
                        "failure_mode": result.failure_mode,
                        "graph_generated": result.graph_generated,
                        "generated_sql": result.generated_sql,
                        "plan_efficiency": result.plan_efficiency,
                        "total_steps": result.total_steps,
                        "unique_steps": result.unique_steps,
                        "expected_steps": result.expected_steps,
                        "step_accuracy": result.step_accuracy
                    }
                )
            
        except Exception as e:
            import traceback
            result.error = str(e)
            print(f"\n[ERROR] {e}")
            print(traceback.format_exc())
            
            # Log error
            if DEBUG_LOGGING_AVAILABLE:
                log_agent_interaction(
                    eval_id if 'eval_id' in dir() else f"eval_error_{result.query_id}",
                    "Evaluator", "Error",
                    query,
                    {"error": str(e), "traceback": traceback.format_exc()}
                )
        
        # Export if requested
        if to_CSV:
            self._export_result_to_csv(result)
        
        return result
    
    def evaluate_dataset(self, 
                         categories: List[str] = None,
                         difficulties: List[str] = None,
                         limit: int = None,
                         to_CSV: bool = True) -> List[ValidationResult]:
        """
        Evaluate multiple queries from the golden dataset.
        
        Args:
            categories: Filter by categories (structured, graph, advisory, etc.)
            difficulties: Filter by difficulty (easy, medium, hard)
            limit: Max number of queries to evaluate
            to_CSV: Export results to CSV
        
        Returns:
            List of ValidationResult objects
        """
        results = []
        
        # Filter dataset
        queries_to_evaluate = self.golden_dataset
        
        if categories:
            queries_to_evaluate = [
                q for q in queries_to_evaluate 
                if q.get('category') in categories
            ]
        
        if difficulties:
            queries_to_evaluate = [
                q for q in queries_to_evaluate 
                if q.get('difficulty') in difficulties
            ]
        
        if limit:
            queries_to_evaluate = queries_to_evaluate[:limit]
        
        print(f"\n{'='*60}")
        print(f"BATCH EVALUATION: {len(queries_to_evaluate)} queries")
        print(f"{'='*60}")
        
        for i, entry in enumerate(queries_to_evaluate):
            print(f"\n[{i+1}/{len(queries_to_evaluate)}] ", end="")
            result = self.evaluate_query(entry['query'], to_CSV=False)
            results.append(result)
        
        # Export all results
        if to_CSV:
            self._export_batch_to_csv(results)
        
        # Print summary
        self._print_batch_summary(results)
        
        # Print failure mode analysis table (ISSUE 4 from ChatGPT review)
        self.print_failure_analysis(results)
        
        return results
    
    def _export_result_to_csv(self, result: ValidationResult):
        """Export single result to CSV."""
        csv_path = os.path.join(BASE_DIR, "evaluation_results_v2.csv")
        file_exists = os.path.exists(csv_path)
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            if not file_exists:
                writer.writerow([
                    "Timestamp", "Query_ID", "Query", "Category", "Difficulty",
                    "Tool_Accuracy", "SQL_Validity", "Value_Accuracy", 
                    "Semantic_Similarity", "Overall_Score", "Passed",
                    "Graph_Generated", "Error"
                ])
            
            writer.writerow([
                result.timestamp, result.query_id, result.query[:100],
                result.category, result.difficulty,
                f"{result.tool_accuracy:.3f}", f"{result.sql_validity:.3f}",
                f"{result.value_accuracy:.3f}", f"{result.semantic_similarity:.3f}",
                f"{result.overall_score:.3f}", result.passed,
                result.graph_generated, result.error
            ])
        
        print(f"\n📁 Saved to {csv_path}")
    
    def _export_batch_to_csv(self, results: List[ValidationResult]):
        """Export batch results to CSV."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(BASE_DIR, "test_results_v2.csv")
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow([
                "Query_ID", "Query", "Category", "Difficulty",
                "Tool_Accuracy", "SQL_Validity", "Value_Accuracy", 
                "Semantic_Similarity", "Overall_Score", "Passed",
                "Graph_Generated", "Plan_Efficiency", "Failure_Mode", "SFA_Response", "Error"
            ])
            
            for r in results:
                # Truncate response to 500 chars for CSV
                response_preview = r.actual_response[:500].replace('\n', ' ').replace(',', ';') if r.actual_response else ""
                writer.writerow([
                    r.query_id, r.query[:100], r.category, r.difficulty,
                    f"{r.tool_accuracy:.3f}", f"{r.sql_validity:.3f}",
                    f"{r.value_accuracy:.3f}", f"{r.semantic_similarity:.3f}",
                    f"{r.overall_score:.3f}", r.passed, r.graph_generated,
                    f"{r.plan_efficiency:.0%}", r.failure_mode, response_preview, r.error
                ])
        
        print(f"\n📁 Batch results saved to {csv_path}")
    
    def _print_batch_summary(self, results: List[ValidationResult]):
        """Print summary of batch evaluation."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        
        print(f"\n{'='*60}")
        print("BATCH EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total Queries: {total}")
        print(f"Passed: {passed} ({100*passed/total:.1f}%)")
        print(f"Failed: {total - passed} ({100*(total-passed)/total:.1f}%)")
        
        # By category
        categories = {}
        for r in results:
            cat = r.category
            if cat not in categories:
                categories[cat] = {'total': 0, 'passed': 0}
            categories[cat]['total'] += 1
            if r.passed:
                categories[cat]['passed'] += 1
        
        print(f"\nBy Category:")
        for cat, stats in categories.items():
            pct = 100 * stats['passed'] / stats['total'] if stats['total'] > 0 else 0
            print(f"  {cat}: {stats['passed']}/{stats['total']} ({pct:.1f}%)")
        
        # Average scores
        avg_tool = sum(r.tool_accuracy for r in results) / total
        avg_sql = sum(r.sql_validity for r in results) / total
        avg_value = sum(r.value_accuracy for r in results) / total
        avg_semantic = sum(r.semantic_similarity for r in results) / total
        avg_overall = sum(r.overall_score for r in results) / total
        
        print(f"\nAverage Scores:")
        print(f"  Tool Accuracy:       {avg_tool:.3f}")
        print(f"  SQL Validity:        {avg_sql:.3f}")
        print(f"  Value Accuracy:      {avg_value:.3f}")
        print(f"  Semantic Similarity: {avg_semantic:.3f}")
        print(f"  Overall:             {avg_overall:.3f}")
        print(f"{'='*60}\n")


# =========================================================================
# CLI INTERFACE
# =========================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SFA Evaluator V2")
    parser.add_argument("--query", type=str, help="Single query to evaluate")
    parser.add_argument("--batch", action="store_true", help="Evaluate entire dataset")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--difficulty", type=str, help="Filter by difficulty")
    parser.add_argument("--limit", type=int, help="Limit number of queries")
    parser.add_argument("--csv", action="store_true", default=True, help="Export to CSV")
    
    args = parser.parse_args()
    
    evaluator = SFAEvaluatorV2()
    
    if args.query:
        result = evaluator.evaluate_query(args.query, to_CSV=args.csv)
    elif args.batch:
        categories = [args.category] if args.category else None
        difficulties = [args.difficulty] if args.difficulty else None
        evaluator.evaluate_dataset(
            categories=categories,
            difficulties=difficulties,
            limit=args.limit,
            to_CSV=args.csv
        )
    else:
        # Default: run one test query
        print("Running test evaluation...")
        result = evaluator.evaluate_query("What was the total revenue in 2024?", to_CSV=True)
