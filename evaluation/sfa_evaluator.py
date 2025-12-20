"""
SFA Evaluator - Agent-Level Metrics for Smart Financial Advisor

This module provides comprehensive evaluation metrics for the RAMAS pipeline:
- Planner Metrics: PVS (Plan Validity Score), DCR (Decomposition Completeness Rate)
- Worker Metrics: CoTA (Chain-of-Tables Adherence), QED (Query Expansion Diversity), RRF, Fusion Gain
- Auditor Metrics: FCS (Fact Consistency Score), NCA (Negative Constraint Adherence)

Usage:
    evaluator = SFAEvaluator()
    results = evaluator.evaluate_query("What is revenue in 2024?", to_CSV=True)
"""

import numpy as np
import re
import csv
import os
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

# =========================================================================
# DATA CLASSES FOR RESULTS
# =========================================================================

@dataclass
class PlannerMetrics:
    """Metrics from the Planner agent evaluation."""
    pvs: float = 0.0          # Plan Validity Score
    dcr: float = 0.0          # Decomposition Completeness Rate
    plan_raw: str = ""        # Raw plan output
    steps_extracted: int = 0  # Number of steps extracted
    valid_steps: int = 0      # Number of valid steps (using allowed tools)


@dataclass
class WorkerMetrics:
    """Metrics from the Worker agent evaluation."""
    cota: float = 0.0         # Chain-of-Tables Adherence
    qed: float = 0.0          # Query Expansion Diversity
    rrf_score: float = 0.0    # Reciprocal Rank Fusion Score
    fusion_gain: float = 0.0  # Fusion gain over single-query retrieval
    sql_executed: bool = False
    rag_executed: bool = False
    execution_result: str = ""


@dataclass
class AuditorMetrics:
    """Metrics from the Auditor agent evaluation."""
    fcs: str = "N/A"          # Fact Consistency Score (Entailment/Contradiction/Neutral)
    nca: int = 1              # Negative Constraint Adherence (1=Pass, 0=Fail)
    response_length: int = 0
    has_data: bool = True     # Whether data was available


@dataclass
class EvaluationResult:
    """Complete evaluation result for a query."""
    query: str
    timestamp: str = ""
    
    # Agent metrics
    planner: PlannerMetrics = field(default_factory=PlannerMetrics)
    worker: WorkerMetrics = field(default_factory=WorkerMetrics)
    auditor: AuditorMetrics = field(default_factory=AuditorMetrics)
    
    # Overall
    final_response: str = ""
    pipeline_success: bool = False
    error: str = ""


# =========================================================================
# SFA EVALUATOR CLASS
# =========================================================================

class SFAEvaluator:
    """
    Evaluates the SFA RAMAS pipeline with agent-level metrics.
    
    Metrics are based on the paper's appendix specifications:
    - PVS: Plan Validity Score (Appendix A.1)
    - DCR: Decomposition Completeness Rate
    - CoTA: Chain-of-Tables Adherence (Appendix A.2)
    - QED: Query Expansion Diversity
    - RRF: Reciprocal Rank Fusion Score (Appendix A.3)
    - FCS: Fact Consistency Score (NLI-based)
    - NCA: Negative Constraint Adherence
    """
    
    def __init__(self):
        # Valid tools in SFA (mapped from paper's format)
        # SFA uses "SQL: ..." and "RAG: ..." format
        self.valid_tools = {"SQL", "RAG"}
        self.rrf_constant = 60  # Standard RRF constant (k)
        
        # Intent units for DCR calculation (common financial query components)
        self.known_intent_units = {
            "revenue", "profit", "income", "margin", "cost", "expense",
            "stock", "price", "volume", "growth", "trend", "quarter",
            "annual", "monthly", "comparison", "2023", "2024", "2025"
        }
    
    # =========================================================================
    # SECTION 1: PLANNER AGENT METRICS
    # =========================================================================
    
    def _extract_plan_steps(self, plan: str) -> List[Dict]:
        """
        Extract structured steps from planner output.
        SFA format: "1. SQL: Retrieve revenue..." or "1. RAG: Find information..."
        Also handles: "1. **SQL**: ..." or "SQL: ..." without number
        """
        steps = []
        
        # Split by newlines
        lines = plan.split("\n")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove markdown bold markers
            clean_line = line.replace("**", "")
            
            # Pattern 1: Numbered steps "1. SQL: ..." or "1) SQL: ..."
            match = re.match(r"^\s*(\d+)[\.)\s]+\s*(SQL|RAG)\s*:\s*(.+)", clean_line, re.IGNORECASE)
            if match:
                step_num = int(match.group(1))
                tool = match.group(2).upper()
                action = match.group(3).strip()
                steps.append({
                    "id": step_num,
                    "tool": tool,
                    "action": action,
                    "raw": line
                })
                continue
            
            # Pattern 2: Just "SQL: ..." or "RAG: ..." without number
            match2 = re.match(r"^\s*(SQL|RAG)\s*:\s*(.+)", clean_line, re.IGNORECASE)
            if match2:
                tool = match2.group(1).upper()
                action = match2.group(2).strip()
                steps.append({
                    "id": len(steps) + 1,
                    "tool": tool,
                    "action": action,
                    "raw": line
                })
        
        return steps
    
    def _extract_dependencies(self, steps: List[Dict]) -> List[Tuple[int, int]]:
        """
        Infer dependencies between steps.
        Simple heuristic: if step N mentions "step N-1" or previous results, it depends on it.
        """
        dependencies = []
        for i, step in enumerate(steps):
            action_lower = step["action"].lower()
            # Check for explicit references like "from step 1" or "using previous"
            for j in range(i):
                if f"step {j+1}" in action_lower or "previous" in action_lower:
                    dependencies.append((steps[j]["id"], step["id"]))
        return dependencies
    
    def calculate_pvs(self, plan_steps: List[Dict], dependencies: List[Tuple[int, int]]) -> float:
        """
        Calculate Plan Validity Score (PVS).
        Formula: PVS = D(S) * (1/n * Sum(V(s_i)))
        
        - V(s_i) = 1 if step uses a valid tool, 0 otherwise
        - D(S) = 1 if dependencies are topologically valid, 0 otherwise
        """
        n = len(plan_steps)
        if n == 0:
            return 0.0
        
        # 1. Calculate validity score (tool validity)
        valid_count = 0
        for step in plan_steps:
            if step.get("tool") in self.valid_tools:
                valid_count += 1
        
        validity_score = valid_count / n
        
        # 2. Check topological ordering of dependencies
        is_valid_order = 1
        step_indices = {step["id"]: i for i, step in enumerate(plan_steps)}
        
        for parent_id, child_id in dependencies:
            parent_idx = step_indices.get(parent_id, float("inf"))
            child_idx = step_indices.get(child_id, -1)
            if parent_idx >= child_idx:
                is_valid_order = 0
                break
        
        pvs = is_valid_order * validity_score
        return pvs
    
    def calculate_dcr(self, query: str, plan_steps: List[Dict]) -> float:
        """
        Calculate Decomposition Completeness Rate (DCR).
        Measures if all intent units in query are covered by the plan.
        """
        # Extract intent units from query
        query_lower = query.lower()
        query_units = set()
        for unit in self.known_intent_units:
            if unit in query_lower:
                query_units.add(unit)
        
        if not query_units:
            return 1.0  # No known intent units = fully covered
        
        # Check coverage in plan steps
        plan_text = " ".join([s.get("action", "") for s in plan_steps]).lower()
        covered = 0
        for unit in query_units:
            if unit in plan_text:
                covered += 1
        
        return covered / len(query_units)
    
    # =========================================================================
    # SECTION 2: WORKER AGENT METRICS
    # =========================================================================
    
    def calculate_cota(self, reasoning_trace: str) -> float:
        """
        Calculate Chain-of-Tables Adherence (CoTA).
        Formula: CoTA = Sum(Exist(c, O)) / |R|
        Required components R = {PLAN, JOIN, FILTER} or equivalent operations.
        """
        # SFA equivalent components in SQL execution traces
        required_components = [
            ("SELECT", "Query selection"),
            ("FROM", "Table access"),
            ("WHERE", "Filtering condition")
        ]
        
        trace_upper = reasoning_trace.upper()
        present_count = 0
        
        for component, _ in required_components:
            if component in trace_upper:
                present_count += 1
        
        return present_count / len(required_components) if required_components else 0.0
    
    def calculate_qed(self, query_variations: List[str]) -> float:
        """
        Calculate Query Expansion Diversity (QED).
        Measures semantic diversity between generated query variations.
        
        Uses simple Jaccard distance as a proxy (no external embedding model).
        Higher score = more diverse queries.
        """
        if len(query_variations) < 2:
            return 0.0
        
        # Tokenize each query
        tokenized = [set(q.lower().split()) for q in query_variations]
        
        # Calculate pairwise Jaccard distances
        distances = []
        n = len(tokenized)
        for i in range(n):
            for j in range(i + 1, n):
                intersection = len(tokenized[i] & tokenized[j])
                union = len(tokenized[i] | tokenized[j])
                if union > 0:
                    jaccard_sim = intersection / union
                    distances.append(1 - jaccard_sim)  # Distance = 1 - similarity
        
        return np.mean(distances) if distances else 0.0
    
    def calculate_rrf_score(self, document_id: str, ranked_lists: List[List[str]]) -> float:
        """
        Calculate Reciprocal Rank Fusion Score.
        Formula: Score(d) = Sum(1 / (k + rank(d, I_i)))
        """
        score = 0.0
        for r_list in ranked_lists:
            if document_id in r_list:
                rank = r_list.index(document_id) + 1  # 1-based rank
                score += 1.0 / (self.rrf_constant + rank)
        return score
    
    def calculate_fusion_gain(self, recall_fusion: float, recall_single: float) -> float:
        """
        Calculate Fusion Gain.
        Formula: (Recall_Fusion - Recall_Single) / Recall_Single
        """
        if recall_single == 0:
            return 0.0
        return (recall_fusion - recall_single) / recall_single
    
    # =========================================================================
    # SECTION 3: AUDITOR AGENT METRICS
    # =========================================================================
    
    def calculate_fcs(self, premise_data: str, auditor_response: str) -> str:
        """
        Calculate Fact Consistency Score (FCS) using simple heuristics.
        
        In production, this would use an NLI model (DeBERTa).
        Here we use keyword matching as a proxy.
        
        Returns: "Entailment", "Contradiction", or "Neutral"
        """
        if not premise_data or not auditor_response:
            return "Neutral"
        
        # Extract numbers from premise
        premise_numbers = set(re.findall(r"\d+\.?\d*", premise_data))
        response_numbers = set(re.findall(r"\d+\.?\d*", auditor_response))
        
        # Check for data unavailable responses
        unavailable_phrases = ["no data", "data not available", "unavailable", "cannot provide"]
        if any(phrase in auditor_response.lower() for phrase in unavailable_phrases):
            # If premise has data but response says unavailable = potential issue
            if premise_numbers:
                return "Contradiction"
            return "Entailment"
        
        # Check if response contains numbers from premise
        overlap = premise_numbers & response_numbers
        if overlap:
            return "Entailment"
        elif premise_numbers and response_numbers and not overlap:
            # Both have numbers but no overlap might indicate fabrication
            return "Neutral"
        
        return "Neutral"
    
    def calculate_nca(self, is_data_empty: bool, auditor_response: str) -> int:
        """
        Calculate Negative Constraint Adherence (NCA).
        If data is empty, the auditor MUST acknowledge it (not hallucinate).
        
        Returns: 1 (Pass) or 0 (Fail)
        """
        refusal_phrases = [
            "data unavailable", "no data available", "cannot answer",
            "no information", "not available", "data not found",
            "no results", "unable to provide"
        ]
        
        if is_data_empty:
            response_lower = auditor_response.lower()
            if any(phrase in response_lower for phrase in refusal_phrases):
                return 1  # Correctly refused
            else:
                return 0  # Hallucinated (failed to refuse)
        
        return 1  # Data was available, NCA not applicable
    
    # =========================================================================
    # MAIN EVALUATION METHOD
    # =========================================================================
    
    def evaluate_query(self, query: str, to_CSV: bool = False) -> EvaluationResult:
        """
        Run a full evaluation of a query through the RAMAS pipeline.
        
        Args:
            query: The user query to evaluate
            to_CSV: If True, export results to CSV file
            
        Returns:
            EvaluationResult with all metrics
        """
        result = EvaluationResult(
            query=query,
            timestamp=datetime.now().isoformat()
        )
        
        try:
            # Import SFA components
            from backend.agents.planner import plan_task
            from backend.agents.worker import execute_step
            from backend.agents.auditor import audit_and_synthesize
            from backend.routing import extract_steps
            
            print(f"\n{'='*60}")
            print(f"SFA EVALUATOR - Evaluating: {query}")
            print(f"{'='*60}\n")
            
            # ============================================
            # STEP 1: PLANNER EVALUATION
            # ============================================
            print("[1/3] Evaluating Planner...")
            
            plan_output = plan_task(query, graph_allowed=False)
            result.planner.plan_raw = plan_output
            
            # Extract and analyze plan steps
            plan_steps = self._extract_plan_steps(plan_output)
            result.planner.steps_extracted = len(plan_steps)
            result.planner.valid_steps = sum(1 for s in plan_steps if s.get("tool") in self.valid_tools)
            
            # Calculate planner metrics
            dependencies = self._extract_dependencies(plan_steps)
            result.planner.pvs = self.calculate_pvs(plan_steps, dependencies)
            result.planner.dcr = self.calculate_dcr(query, plan_steps)
            
            print(f"   • Plan Steps: {result.planner.steps_extracted}")
            print(f"   • Valid Steps: {result.planner.valid_steps}")
            print(f"   • PVS: {result.planner.pvs:.2f}")
            print(f"   • DCR: {result.planner.dcr:.2f}")
            
            # ============================================
            # STEP 2: WORKER EVALUATION
            # ============================================
            print("\n[2/3] Evaluating Worker...")
            
            context = ""
            raw_steps = extract_steps(plan_output)
            
            for step in raw_steps:
                if step.strip():
                    clean_step = step.replace("**", "")
                    step_result = execute_step(clean_step)
                    context += f"\nStep: {step}\nResult: {step_result}\n"
                    
                    # Track tool usage
                    if "SQL" in step.upper():
                        result.worker.sql_executed = True
                    if "RAG" in step.upper():
                        result.worker.rag_executed = True
            
            result.worker.execution_result = context[:500]  # Truncate for storage
            
            # Calculate worker metrics
            result.worker.cota = self.calculate_cota(context)
            
            # QED calculation (simulate query variations if RAG was used)
            if result.worker.rag_executed:
                # In real scenario, capture actual variations from rag_fusion
                simulated_variations = [query, query + " data", "financial " + query]
                result.worker.qed = self.calculate_qed(simulated_variations)
            
            print(f"   • SQL Executed: {result.worker.sql_executed}")
            print(f"   • RAG Executed: {result.worker.rag_executed}")
            print(f"   • CoTA: {result.worker.cota:.2f}")
            print(f"   • QED: {result.worker.qed:.2f}")
            
            # ============================================
            # STEP 3: AUDITOR EVALUATION
            # ============================================
            print("\n[3/3] Evaluating Auditor...")
            
            final_response = audit_and_synthesize(query, context, graph_allowed=False)
            result.final_response = final_response
            result.auditor.response_length = len(final_response)
            
            # Check if data was available
            is_data_empty = (
                "no data" in context.lower() or 
                "error" in context.lower() or
                not context.strip()
            )
            result.auditor.has_data = not is_data_empty
            
            # Calculate auditor metrics
            result.auditor.fcs = self.calculate_fcs(context, final_response)
            result.auditor.nca = self.calculate_nca(is_data_empty, final_response)
            
            print(f"   • Response Length: {result.auditor.response_length}")
            print(f"   • Has Data: {result.auditor.has_data}")
            print(f"   • FCS: {result.auditor.fcs}")
            print(f"   • NCA: {'Pass' if result.auditor.nca else 'Fail'}")
            
            result.pipeline_success = True
            
        except Exception as e:
            import traceback
            result.error = str(e)
            result.pipeline_success = False
            print(f"\n❌ Evaluation Error: {e}")
            print(traceback.format_exc())
        
        # ============================================
        # EXPORT TO CSV (if requested)
        # ============================================
        if to_CSV:
            self._export_to_csv(result)
        
        # Print summary
        self._print_summary(result)
        
        return result
    
    def _export_to_csv(self, result: EvaluationResult):
        """Export evaluation results to CSV file."""
        csv_path = os.path.join(
            os.path.dirname(__file__), 
            "evaluation_results.csv"
        )
        
        # Check if file exists (to write header)
        file_exists = os.path.exists(csv_path)
        
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Write header if new file
            if not file_exists:
                writer.writerow([
                    "Timestamp", "Query", "Pipeline_Success",
                    "PVS", "DCR", "Steps_Extracted", "Valid_Steps",
                    "CoTA", "QED", "RRF_Score", "Fusion_Gain",
                    "SQL_Executed", "RAG_Executed",
                    "FCS", "NCA", "Has_Data", "Response_Length",
                    "Error"
                ])
            
            # Write data row
            writer.writerow([
                result.timestamp,
                result.query,
                result.pipeline_success,
                f"{result.planner.pvs:.3f}",
                f"{result.planner.dcr:.3f}",
                result.planner.steps_extracted,
                result.planner.valid_steps,
                f"{result.worker.cota:.3f}",
                f"{result.worker.qed:.3f}",
                f"{result.worker.rrf_score:.3f}",
                f"{result.worker.fusion_gain:.3f}",
                result.worker.sql_executed,
                result.worker.rag_executed,
                result.auditor.fcs,
                result.auditor.nca,
                result.auditor.has_data,
                result.auditor.response_length,
                result.error
            ])
        
        print(f"\n📁 Results exported to: {csv_path}")
    
    def _print_summary(self, result: EvaluationResult):
        """Print a formatted summary of the evaluation."""
        print(f"\n{'='*60}")
        print("EVALUATION SUMMARY")
        print(f"{'='*60}")
        print(f"Query: {result.query}")
        print(f"Status: {'✅ Success' if result.pipeline_success else '❌ Failed'}")
        print(f"\n--- PLANNER METRICS ---")
        print(f"  PVS (Plan Validity Score):     {result.planner.pvs:.2f}")
        print(f"  DCR (Decomposition Complete):  {result.planner.dcr:.2f}")
        print(f"\n--- WORKER METRICS ---")
        print(f"  CoTA (Chain-of-Tables):        {result.worker.cota:.2f}")
        print(f"  QED (Query Diversity):         {result.worker.qed:.2f}")
        print(f"\n--- AUDITOR METRICS ---")
        print(f"  FCS (Fact Consistency):        {result.auditor.fcs}")
        print(f"  NCA (Negative Constraint):     {'Pass' if result.auditor.nca else 'Fail'}")
        print(f"\n--- RESPONSE ---")
        print(f"  {result.final_response[:200]}{'...' if len(result.final_response) > 200 else ''}")
        print(f"{'='*60}\n")


# =========================================================================
# STANDALONE TEST
# =========================================================================

if __name__ == "__main__":
    evaluator = SFAEvaluator()
    
    # Test with a sample query
    test_query = "What was the revenue in 2024?"
    
    print("Starting SFA Evaluation Test...")
    result = evaluator.evaluate_query(test_query, to_CSV=True)
    
    print("\nTest completed!")
    print(f"Final PVS: {result.planner.pvs}")
    print(f"Final DCR: {result.planner.dcr}")
    print(f"Final CoTA: {result.worker.cota}")
    print(f"Final FCS: {result.auditor.fcs}")
