"""
Updated Full RAGAS-style Evaluation Pipeline
- Improved numeric & entity matching, safer thresholds, and proper use of retrieved contexts vs ground truth.
- Leave the four lists at the bottom empty to hardcode later (as requested).

Dependencies:
    pip install sentence-transformers==2.2.2 spacy==3.5.4 openpyxl rapidfuzz pandas numpy python-dateutil

Notes:
 - Provide `queries`, `ground_truths`, `chatbot_answers`, and `retrieved_contexts_batch`
   lists aligned by index. retrieved_contexts_batch should be a list of lists (top-k passages).
 - By default ground truth is NOT used as retrieved context. If you want that behavior,
   set use_ground_truth_as_context=True in the example usage section.
"""

import re
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import spacy
from rapidfuzz import fuzz, process
from openpyxl import Workbook
from datetime import datetime

# ----------------------------
# CONFIG (tweakable)
# ----------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
SIM_THRESHOLD = 0.55        # lowered semantic threshold to be less strict
NUM_TOLERANCE = 0.05        # 5% relative tolerance for numeric equality
TOPK_CONTEXT = 5
RAGAS_WEIGHTS = {
    "faithfulness": 0.25,
    "answer_relevance": 0.20,
    "context_recall": 0.20,
    "context_precision": 0.10,
    "answer_correctness": 0.25
}
PASS_THRESHOLD = 0.55       # final PASS/FAIL threshold (less strict than before)

# ----------------------------
# LOAD MODELS
# ----------------------------
print("Loading models...")
embedder = SentenceTransformer(EMBEDDING_MODEL)
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")
print("Models loaded.")

# ----------------------------
# UTILITIES: numeric extraction + normalization
# ----------------------------
def extract_numeric_expressions(text: str) -> List[Tuple[float, str]]:
    """
    Returns list of (value_in_float, original_unit_str)
    Handles $219.66B, 219.66 B, 219,660,000,000, $29.94 Billion, 29.94bn, etc.
    """
    if not text:
        return []
    text_u = text.upper().replace(',', '')
    results: List[Tuple[float, str]] = []
    # capture numbers with optional unit
    for m in re.finditer(r'\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(B|BN|BILLION|M|MN|MILLION|K|THOUSAND)?', text_u):
        num_str = m.group(1)
        unit = m.group(2) or ''
        try:
            val = float(num_str)
        except:
            continue
        unit = unit.strip()
        if unit in ('B', 'BN', 'BILLION'):
            val *= 1e9
        elif unit in ('M', 'MN', 'MILLION'):
            val *= 1e6
        elif unit in ('K', 'THOUSAND'):
            val *= 1e3
        results.append((val, unit or ''))
    return results

def pretty_number(x: float) -> str:
    if x >= 1e9:
        return f"${x/1e9:.2f}B"
    if x >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x:.2f}"

# ----------------------------
# ENTITY & NUMERIC MAPPING
# ----------------------------
def extract_entities(text: str) -> List[str]:
    """Return list of PERSON/ORG/GPE/PRODUCT entities lowercased (deduplicated)."""
    if not text:
        return []
    doc = nlp(str(text))
    ents = [ent.text.lower() for ent in doc.ents if ent.label_ in ("ORG", "PERSON", "GPE", "PRODUCT")]
    if not ents:
        # fallback: capture capitalized single tokens
        caps = re.findall(r'\b([A-Z][a-zA-Z0-9&\.\-]{1,30})\b', text)
        ents = [c.lower() for c in caps]
    seen = set()
    out: List[str] = []
    for e in ents:
        if e in seen:
            continue
        seen.add(e)
        out.append(e)
    return out

def map_numbers_to_entities(text: str) -> Dict[str, List[float]]:
    """
    Map numeric values to nearby entities at sentence level.
    Returns dict: {entity_name: [numbers]}
    """
    out: Dict[str, List[float]] = {}
    if not text:
        return out
    sentences = re.split(r'[.;]\s*', text)
    for sent in sentences:
        ents = extract_entities(sent)
        nums = [v for (v, u) in extract_numeric_expressions(sent)]
        if ents and nums:
            for e in ents:
                out.setdefault(e, []).extend(nums)
        else:
            nums_all = [v for (v, u) in extract_numeric_expressions(sent)]
            if nums_all:
                caps = re.findall(r'\b([A-Z][a-zA-Z0-9&\.\-]{1,30})\b', text)
                if caps:
                    ent = caps[0].lower()
                    out.setdefault(ent, []).extend(nums_all)
    return out

# ----------------------------
# SEMANTIC SIMILARITY
# ----------------------------
def semantic_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    emb_a = embedder.encode(a, convert_to_tensor=True)
    emb_b = embedder.encode(b, convert_to_tensor=True)
    sim = util.pytorch_cos_sim(emb_a, emb_b).item()
    return float(sim)

# ----------------------------
# RAGAS DIMENSIONS IMPLEMENTATION
# ----------------------------
def score_answer_relevance(query: str, answer: str) -> float:
    sim = semantic_similarity(query, answer)
    q_words = set(re.findall(r'\w+', query.lower()))
    a_words = set(re.findall(r'\w+', answer.lower()))
    overlap = len(q_words & a_words) / (len(q_words) + 1e-9)
    return 0.6 * sim + 0.4 * overlap

def score_answer_correctness(gt: str, answer: str) -> float:
    """
    Combines embedding semantic similarity, fuzzy textual match, and improved numeric/entity-aware matching.
    If numeric mapping strongly matches, boost overall correctness (so numeric agreement dominates).
    """
    sem = semantic_similarity(gt, answer)
    fuzzy = fuzz.token_sort_ratio(str(gt), str(answer)) / 100.0

    gt_map = map_numbers_to_entities(gt)
    cb_map = map_numbers_to_entities(answer)

    # Improved numeric matching
    num_score = 0.0
    if gt_map:
        entity_scores: List[float] = []
        for ent, gt_vals in gt_map.items():
            # find best matching key in cb_map
            if cb_map:
                match = process.extractOne(ent, list(cb_map.keys()), scorer=fuzz.token_sort_ratio)
            else:
                match = None
            if match:
                matched_key, match_score = match[0], match[1]
            else:
                matched_key, match_score = None, 0

            if matched_key and match_score >= 55:  # relaxed threshold
                cb_vals = cb_map.get(matched_key, [])
                best_val_score = 0.0
                for g in gt_vals:
                    for c in cb_vals:
                        if g == 0 or c == 0:
                            continue
                        # exact relative-difference shortcut
                        rel_diff = abs(g - c) / max(g, c)
                        if rel_diff <= NUM_TOLERANCE:
                            this_score = 1.0
                        else:
                            this_score = min(g, c) / max(g, c)
                        if this_score > best_val_score:
                            best_val_score = this_score
                entity_scores.append(best_val_score)
            else:
                # try fallback: if cb_map has any entity that fuzzily matches part of ent
                fallback_best = 0.0
                for cb_ent in cb_map.keys():
                    r = fuzz.partial_ratio(ent, cb_ent)
                    if r > fallback_best:
                        fallback_best = r
                if fallback_best >= 65:
                    # partial match exists, but no number mapped -> penalize less
                    entity_scores.append(0.5)
                else:
                    entity_scores.append(0.0)
        num_score = sum(entity_scores) / len(entity_scores) if entity_scores else 0.0
    else:
        # No numeric GT; if answer contains numbers, it's suspicious (lower), else neutral
        num_score = 1.0 if not extract_numeric_expressions(answer) else 0.6

    # If numeric agreement is very strong => force high correctness (numbers dominate)
    if num_score >= 0.95:
        # ensure returned score is at least 0.85
        aggregated = 0.5 * sem + 0.2 * fuzzy + 0.3 * num_score
        return max(0.85, aggregated)

    # Otherwise weighted aggregate
    return 0.5 * sem + 0.2 * fuzzy + 0.3 * num_score

def score_context_recall(answer: str, retrieved_contexts: List[str]) -> float:
    if not retrieved_contexts:
        return 0.0
    sims = [semantic_similarity(answer, c) for c in retrieved_contexts]
    sim_score = max(sims) if sims else 0.0

    answer_nums = [v for (v, u) in extract_numeric_expressions(answer)]
    if not answer_nums:
        num_cov = 1.0
    else:
        found = 0
        total = len(answer_nums)
        for an in answer_nums:
            matched = False
            for c in retrieved_contexts:
                for (v, u) in extract_numeric_expressions(c):
                    if max(v, an) == 0:
                        continue
                    ratio = min(v, an) / max(v, an)
                    if ratio >= (1 - NUM_TOLERANCE):
                        matched = True
                        break
                if matched:
                    break
            if matched:
                found += 1
        num_cov = found / total
    return 0.7 * sim_score + 0.3 * num_cov

def score_context_precision(answer: str, retrieved_contexts: List[str]) -> float:
    if not retrieved_contexts:
        return 0.0
    sims = np.array([semantic_similarity(answer, c) for c in retrieved_contexts])
    if sims.sum() == 0:
        return 0.0
    probs = sims / sims.sum()
    used_mask = sims >= (SIM_THRESHOLD * 0.5)
    precision = probs[used_mask].sum()
    return float(precision)

def score_faithfulness(answer: str, retrieved_contexts: List[str]) -> float:
    if not answer:
        return 0.0
    sentences = [s.strip() for s in re.split(r'[.;]\s*', answer) if s.strip()]
    if not sentences:
        return 0.0
    supp_count = 0
    for s in sentences:
        sims = [semantic_similarity(s, c) for c in retrieved_contexts] if retrieved_contexts else [0.0]
        best = max(sims) if sims else 0.0
        s_nums = [v for (v, u) in extract_numeric_expressions(s)]
        numeric_ok = True
        if s_nums:
            numeric_ok = False
            for c in retrieved_contexts:
                for (v, u) in extract_numeric_expressions(c):
                    for s_n in s_nums:
                        if max(v, s_n) == 0:
                            continue
                        ratio = min(v, s_n) / max(v, s_n)
                        if ratio >= (1 - NUM_TOLERANCE):
                            numeric_ok = True
                            break
                    if numeric_ok:
                        break
                if numeric_ok:
                    break
        if (best >= SIM_THRESHOLD and numeric_ok) or (best >= (SIM_THRESHOLD + 0.1)):
            supp_count += 1
    return supp_count / len(sentences)

# ----------------------------
# Pipeline orchestrator
# ----------------------------
def evaluate_ragas_batch(
    queries: List[str],
    ground_truths: List[str],
    chatbot_answers: List[str],
    retrieved_contexts_batch: Optional[List[List[str]]] = None,
    use_ground_truth_as_context: bool = False
) -> pd.DataFrame:
    """
    Evaluate aligned lists. If use_ground_truth_as_context=True, the ground truth string
    will be appended to retrieved_contexts for faithfulness scoring (not recommended for strict eval).
    """
    n = len(queries)
    if len(ground_truths) != n or len(chatbot_answers) != n:
        raise ValueError("queries, ground_truths, and chatbot_answers must have same length")
    if not retrieved_contexts_batch:
        retrieved_contexts_batch = [[] for _ in range(n)]
    if len(retrieved_contexts_batch) != n:
        raise ValueError("retrieved_contexts_batch must be same length as queries (or None)")

    rows: List[Dict[str, Any]] = []
    for i, (q, gt, cb, contexts) in enumerate(zip(queries, ground_truths, chatbot_answers, retrieved_contexts_batch)):
        # If requested, include ground truth as an extra context (useful for debugging only)
        contexts_used = list(contexts)[:]  # copy
        if use_ground_truth_as_context and gt:
            contexts_used = contexts_used + [gt]

        ans_rel = score_answer_relevance(q, cb)
        ans_corr = score_answer_correctness(gt, cb)
        ctx_recall = score_context_recall(cb, contexts_used)
        ctx_prec = score_context_precision(cb, contexts_used)
        faith = score_faithfulness(cb, contexts_used)

        overall = (
            RAGAS_WEIGHTS['faithfulness'] * faith +
            RAGAS_WEIGHTS['answer_relevance'] * ans_rel +
            RAGAS_WEIGHTS['context_recall'] * ctx_recall +
            RAGAS_WEIGHTS['context_precision'] * ctx_prec +
            RAGAS_WEIGHTS['answer_correctness'] * ans_corr
        )

        pass_fail = "PASS" if overall >= PASS_THRESHOLD else "FAIL"

        rows.append({
            "index": i + 1,
            "query": q,
            "ground_truth": gt,
            "chatbot_answer": cb,
            "answer_relevance": round(ans_rel, 4),
            "answer_correctness": round(ans_corr, 4),
            "context_recall": round(ctx_recall, 4),
            "context_precision": round(ctx_prec, 4),
            "faithfulness": round(faith, 4),
            "overall": round(overall, 4),
            "pass_fail": pass_fail
        })

    df = pd.DataFrame(rows)
    return df

# ----------------------------
# Example usage (four lists intentionally left EMPTY for you to hardcode)
# ----------------------------
if __name__ == "__main__":
    # <-- replace these four lists with your actual data to run -->
    queries: List[str] = [
    "Apple revenue",
    "Microsoft revenue",
    "Apple vs Microsoft revenue",
    "Net income of Apple",
    "Total assets of Microsoft",
    "Compare Apple and Tesla revenue",
    "Top 5 companies by revenue",
    "Apple gross profit",
    "Microsoft operating income",
    "Apple cash and equivalents"
]

    ground_truths: List[str] = [
        "Apple Inc revenue (2025-03-31): $219.66B",
        "Microsoft Corp revenue (2025-03-31): $205.28B",
        "Apple: $219.66B, Microsoft: $205.28B. Apple has higher revenue.",
        "Apple Inc net income (2025-03-31): $61.11B",
        "Microsoft Corp total assets: $562.62B",
        "Apple: $219.66B, Tesla: $19.34B",
        "Price T Rowe Group Inc ($1620.30B), Mckesson Corp ($359.05B), Apple Inc ($219.66B), Microsoft Corp ($205.28B), Costco Wholesale Corp /New ($189.08B)",
        "Apple Inc gross profit: $103.14B",
        "Microsoft Corp operating income: $94.20B",
        "Apple Inc cash: $28.16B"
    ]

    chatbot_answers: List[str] = [
        "Apple revenue: $219.66B (2025-03-31)",
        "Microsoft revenue: $205.28B (2025-03-31)",
        "Apple revenue: $219.66B (2025-03-31)  Microsoft revenue: $205.28B (2025-03-31)",
        "Apple: $61.11B (2025-03-31)",
        "Microsoft: $562.62B (2025-03-31)",
        "Apple revenue: $219.66B (2025-03-31) Tesla revenue: $19.34B (2025-03-31)",
        "Apple: $365.82B (2022-09-30)  Microsoft: $198.27B (2022-06-30)  Alphabet: $161.86B (2022-12-31)  Amazon: $121.24B (2022-12-31)  Facebook: $85.96B (2022-12-31)",
        "Apple gross profit: $103.14B (2025-03-31)",
        "Microsoft operating income: $94.20B (2025-03-31)",
        "Apple cash and equivalents: $28.16B (2025-03-31)",
    ]

    # Example retrieved contexts (for faithfulness/context scoring) - ideally this is what your retriever returned
    retrieved_contexts_batch: List[List[str]] = [
    [
        """Database Results
name value ddate
APPLE INC $219.66B 2025-03-31
APPLE INC $166.67B 2025-03-31
APPLE INC $115.98B 2025-03-31
APPLE INC $95.36B 2025-03-31
APPLE INC $92.96B 2025-03-31
APPLE INC $68.71B 2025-03-31
APPLE INC $58.31B 2025-03-31
APPLE INC $52.98B 2025-03-31
APPLE INC $46.84B 2025-03-31
APPLE INC $40.31B 2025-03-31
APPLE INC $34.52B 2025-03-31
APPLE INC $26.64B 2025-03-31
APPLE INC $24.45B 2025-03-31
APPLE INC $19.27B 2025-03-31
APPLE INC $17.58B 2025-03-31
APPLE INC $16.94B 2025-03-31
APPLE INC $16.29B 2025-03-31
APPLE INC $16.00B 2025-03-31
APPLE INC $14.49B 2025-03-31
APPLE INC $7.95B 2025-03-31
APPLE INC $7.52B 2025-03-31
APPLE INC $7.30B 2025-03-31
APPLE INC $7.29B 2025-03-31
APPLE INC $6.40B 2025-03-31
APPLE INC $210.33B 2024-03-31
APPLE INC $163.34B 2024-03-31
APPLE INC $115.67B 2024-03-31
APPLE INC $90.75B 2024-03-31
APPLE INC $87.70B 2024-03-31
APPLE INC $66.89B 2024-03-31
APPLE INC $54.52B 2024-03-31
APPLE INC $46.98B 2024-03-31
APPLE INC $45.96B 2024-03-31
APPLE INC $37.27B 2024-03-31
APPLE INC $37.19B 2024-03-31
APPLE INC $24.12B 2024-03-31
APPLE INC $23.87B 2024-03-31
APPLE INC $19.87B 2024-03-31
APPLE INC $16.89B 2024-03-31
APPLE INC $16.37B 2024-03-31
APPLE INC $15.23B 2024-03-31
APPLE INC $14.03B 2024-03-31
APPLE INC $12.58B 2024-03-31
APPLE INC $7.91B 2024-03-31
APPLE INC $7.45B 2024-03-31
APPLE INC $6.72B 2024-03-31
APPLE INC $6.26B 2024-03-31
APPLE INC $5.56B 2024-03-31"""
    ],
    [
        """Database Results name value ddate MICROSOFT CORP $205.28B 2025-03-31 MICROSOFT CORP $158.47B 2025-03-31 MICROSOFT CORP $122.20B 2025-03-31 MICROSOFT CORP $105.53B 2025-03-31 MICROSOFT CORP $99.75B 2025-03-31 MICROSOFT CORP $87.70B 2025-03-31 MICROSOFT CORP $76.39B 2025-03-31 MICROSOFT CORP $70.56B 2025-03-31 MICROSOFT CORP $70.07B 2025-03-31 MICROSOFT CORP $63.45B 2025-03-31 MICROSOFT CORP $54.75B 2025-03-31 MICROSOFT CORP $46.81B 2025-03-31 MICROSOFT CORP $42.40B 2025-03-31 MICROSOFT CORP $41.20B 2025-03-31 MICROSOFT CORP $36.08B 2025-03-31 MICROSOFT CORP $33.98B 2025-03-31 MICROSOFT CORP $29.94B 2025-03-31 MICROSOFT CORP $26.75B 2025-03-31 MICROSOFT CORP $24.76B 2025-03-31 MICROSOFT CORP $21.88B 2025-03-31 MICROSOFT CORP $17.92B 2025-03-31 MICROSOFT CORP $15.32B 2025-03-31 MICROSOFT CORP $13.37B 2025-03-31 MICROSOFT CORP $13.19B 2025-03-31 MICROSOFT CORP $12.98B 2025-03-31 MICROSOFT CORP $10.29B 2025-03-31 MICROSOFT CORP $5.77B 2025-03-31 MICROSOFT CORP $5.72B 2025-03-31 MICROSOFT CORP $5.69B 2025-03-31 MICROSOFT CORP $5.37B 2025-03-31 MICROSOFT CORP $4.31B 2025-03-31 MICROSOFT CORP $4.14B 2025-03-31 MICROSOFT CORP $3.50B 2025-03-31 MICROSOFT CORP $1.95B 2025-03-31 MICROSOFT CORP $1.93B 2025-03-31 MICROSOFT CORP $1.82B 2025-03-31 MICROSOFT CORP $66.00M 2025-03-31 MICROSOFT CORP $46.00M 2025-03-31 MICROSOFT CORP $180.40B 2024-03-31 MICROSOFT CORP $128.84B 2024-03-31 MICROSOFT CORP $100.80B 2024-03-31 MICROSOFT CORP $92.54B 2024-03-31 MICROSOFT CORP $87.85B 2024-03-31 MICROSOFT CORP $78.19B 2024-03-31 MICROSOFT CORP $63.68B 2024-03-31 MICROSOFT CORP $61.86B 2024-03-31 MICROSOFT CORP $57.92B 2024-03-31 MICROSOFT CORP $56.08B 2024-03-31 MICROSOFT CORP $51.56B 2024-03-31 MICROSOFT CORP $44.78B 2024-03-31 MICROSOFT CORP $38.52B 2024-03-31 MICROSOFT CORP $35.20B 2024-03-31 MICROSOFT CORP $31.44B 2024-03-31 MICROSOFT CORP $30.42B 2024-03-31 MICROSOFT CORP $27.11B 2024-03-31 MICROSOFT CORP $22.14B 2024-03-31 MICROSOFT CORP $20.27B 2024-03-31 MICROSOFT CORP $19.71B 2024-03-31 MICROSOFT CORP $17.08B 2024-03-31 MICROSOFT CORP $16.48B 2024-03-31 MICROSOFT CORP $12.80B 2024-03-31 MICROSOFT CORP $12.60B 2024-03-31 MICROSOFT CORP $12.12B 2024-03-31 MICROSOFT CORP $9.24B 2024-03-31 MICROSOFT CORP $5.72B 2024-03-31 MICROSOFT CORP $5.45B 2024-03-31 MICROSOFT CORP $5.03B 2024-03-31 MICROSOFT CORP $4.97B 2024-03-31 MICROSOFT CORP $4.10B 2024-03-31 MICROSOFT CORP $4.01B 2024-03-31 MICROSOFT CORP $3.06B 2024-03-31 MICROSOFT CORP $1.86B 2024-03-31 MICROSOFT CORP $1.74B 2024-03-31 MICROSOFT CORP $1.65B 2024-03-31 MICROSOFT CORP $32.00M 2024-03-31 MICROSOFT CORP $14.00M 2024-03-31"""
    ],
    [
        """Database Results name value ddate APPLE INC $219.66B 2025-03-31 MICROSOFT CORP $205.28B 2025-03-31 APPLE INC $166.67B 2025-03-31 MICROSOFT CORP $158.47B 2025-03-31 MICROSOFT CORP $122.20B 2025-03-31 APPLE INC $115.98B 2025-03-31 MICROSOFT CORP $105.53B 2025-03-31 MICROSOFT CORP $99.75B 2025-03-31 APPLE INC $95.36B 2025-03-31 APPLE INC $92.96B 2025-03-31 MICROSOFT CORP $87.70B 2025-03-31 MICROSOFT CORP $76.39B 2025-03-31 MICROSOFT CORP $70.56B 2025-03-31 MICROSOFT CORP $70.07B 2025-03-31 APPLE INC $68.71B 2025-03-31 MICROSOFT CORP $63.45B 2025-03-31 APPLE INC $58.31B 2025-03-31 MICROSOFT CORP $54.75B 2025-03-31 APPLE INC $52.98B 2025-03-31 APPLE INC $46.84B 2025-03-31 MICROSOFT CORP $46.81B 2025-03-31 MICROSOFT CORP $42.40B 2025-03-31 MICROSOFT CORP $41.20B 2025-03-31 APPLE INC $40.31B 2025-03-31 MICROSOFT CORP $36.08B 2025-03-31 APPLE INC $34.52B 2025-03-31 MICROSOFT CORP $33.98B 2025-03-31 MICROSOFT CORP $29.94B 2025-03-31 MICROSOFT CORP $26.75B 2025-03-31 APPLE INC $26.64B 2025-03-31 MICROSOFT CORP $24.76B 2025-03-31 APPLE INC $24.45B 2025-03-31 MICROSOFT CORP $21.88B 2025-03-31 APPLE INC $19.27B 2025-03-31 MICROSOFT CORP $17.92B 2025-03-31 APPLE INC $17.58B 2025-03-31 APPLE INC $16.94B 2025-03-31 APPLE INC $16.29B 2025-03-31 APPLE INC $16.00B 2025-03-31 MICROSOFT CORP $15.32B 2025-03-31 APPLE INC $14.49B 2025-03-31 MICROSOFT CORP $13.37B 2025-03-31 MICROSOFT CORP $13.19B 2025-03-31 MICROSOFT CORP $12.98B 2025-03-31 MICROSOFT CORP $10.29B 2025-03-31 APPLE INC $7.95B 2025-03-31 APPLE INC $7.52B 2025-03-31 APPLE INC $7.30B 2025-03-31 APPLE INC $7.29B 2025-03-31 APPLE INC $6.40B 2025-03-31 MICROSOFT CORP $5.77B 2025-03-31 MICROSOFT CORP $5.72B 2025-03-31 MICROSOFT CORP $5.69B 2025-03-31 MICROSOFT CORP $5.37B 2025-03-31 MICROSOFT CORP $4.31B 2025-03-31 MICROSOFT CORP $4.14B 2025-03-31 MICROSOFT CORP $3.50B 2025-03-31 MICROSOFT CORP $1.95B 2025-03-31 MICROSOFT CORP $1.93B 2025-03-31 MICROSOFT CORP $1.82B 2025-03-31 MICROSOFT CORP $66.00M 2025-03-31 MICROSOFT CORP $46.00M 2025-03-31 APPLE INC $210.33B 2024-03-31 MICROSOFT CORP $180.40B 2024-03-31 APPLE INC $163.34B 2024-03-31 MICROSOFT CORP $128.84B 2024-03-31 APPLE INC $115.67B 2024-03-31 MICROSOFT CORP $100.80B 2024-03-31 MICROSOFT CORP $92.54B 2024-03-31 APPLE INC $90.75B 2024-03-31 MICROSOFT CORP $87.85B 2024-03-31 APPLE INC $87.70B 2024-03-31 MICROSOFT CORP $78.19B 2024-03-31 APPLE INC $66.89B 2024-03-31 MICROSOFT CORP $63.68B 2024-03-31 MICROSOFT CORP $61.86B 2024-03-31 MICROSOFT CORP $57.92B 2024-03-31 MICROSOFT CORP $56.08B 2024-03-31 APPLE INC $54.52B 2024-03-31 MICROSOFT CORP $51.56B 2024-03-31 APPLE INC $46.98B 2024-03-31 APPLE INC $45.96B 2024-03-31 MICROSOFT CORP $44.78B 2024-03-31 MICROSOFT CORP $38.52B 2024-03-31 APPLE INC $37.27B 2024-03-31 APPLE INC $37.19B 2024-03-31 MICROSOFT CORP $35.20B 2024-03-31 MICROSOFT CORP $31.44B 2024-03-31 MICROSOFT CORP $30.42B 2024-03-31 MICROSOFT CORP $27.11B 2024-03-31 APPLE INC $24.12B 2024-03-31 APPLE INC $23.87B 2024-03-31 MICROSOFT CORP $22.14B 2024-03-31 MICROSOFT CORP $20.27B 2024-03-31 APPLE INC $19.87B 2024-03-31 MICROSOFT CORP $19.71B 2024-03-31 MICROSOFT CORP $17.08B 2024-03-31 APPLE INC $16.89B 2024-03-31 MICROSOFT CORP $16.48B 2024-03-31 APPLE INC $16.37B 2024-03-31 APPLE INC $15.23B 2024-03-31 APPLE INC $14.03B 2024-03-31 MICROSOFT CORP $12.80B 2024-03-31 MICROSOFT CORP $12.60B 2024-03-31 APPLE INC $12.58B 2024-03-31 MICROSOFT CORP $12.12B 2024-03-31 MICROSOFT CORP $9.24B 2024-03-31 APPLE INC $7.91B 2024-03-31 APPLE INC $7.45B 2024-03-31 APPLE INC $6.72B 2024-03-31 APPLE INC $6.26B 2024-03-31 MICROSOFT CORP $5.72B 2024-03-31 APPLE INC $5.56B 2024-03-31 MICROSOFT CORP $5.45B 2024-03-31 MICROSOFT CORP $5.03B 2024-03-31 MICROSOFT CORP $4.97B 2024-03-31 MICROSOFT CORP $4.10B 2024-03-31 MICROSOFT CORP $4.01B 2024-03-31 MICROSOFT CORP $3.06B 2024-03-31 MICROSOFT CORP $1.86B 2024-03-31 MICROSOFT CORP $1.74B 2024-03-31 MICROSOFT CORP $1.65B 2024-03-31 MICROSOFT CORP $32.00M 2024-03-31 MICROSOFT CORP $14.00M 2024-03-31"""
    ],
    [
        """Database Results name value ddate APPLE INC $61.11B 2025-03-31 APPLE INC $61.11B 2025-03-31 APPLE INC $24.78B 2025-03-31 APPLE INC $24.78B 2025-03-31 APPLE INC $57.55B 2024-03-31 APPLE INC $57.55B 2024-03-31 APPLE INC $23.64B 2024-03-31 APPLE INC $23.64B 2024-03-31"""
    ],
    [
        """Database Results name value ddate MICROSOFT CORP $562.62B 2025-03-31 MICROSOFT CORP $512.16B 2024-06-30"""
    ],
    [
        """Database Results name value ddate APPLE INC $219.66B 2025-03-31 APPLE INC $166.67B 2025-03-31 APPLE INC $115.98B 2025-03-31 APPLE INC $95.36B 2025-03-31 APPLE INC $92.96B 2025-03-31 APPLE INC $68.71B 2025-03-31 APPLE INC $58.31B 2025-03-31 APPLE INC $52.98B 2025-03-31 APPLE INC $46.84B 2025-03-31 APPLE INC $40.31B 2025-03-31 APPLE INC $34.52B 2025-03-31 APPLE INC $26.64B 2025-03-31 APPLE INC $24.45B 2025-03-31 TESLA, INC. $19.34B 2025-03-31 APPLE INC $19.27B 2025-03-31 TESLA, INC. $18.78B 2025-03-31 APPLE INC $17.58B 2025-03-31 APPLE INC $16.94B 2025-03-31 APPLE INC $16.29B 2025-03-31 APPLE INC $16.00B 2025-03-31 APPLE INC $14.49B 2025-03-31 TESLA, INC. $13.97B 2025-03-31 TESLA, INC. $12.93B 2025-03-31 APPLE INC $7.95B 2025-03-31 APPLE INC $7.52B 2025-03-31 APPLE INC $7.30B 2025-03-31 APPLE INC $7.29B 2025-03-31 APPLE INC $6.40B 2025-03-31 TESLA, INC. $2.73B 2025-03-31 TESLA, INC. $2.64B 2025-03-31 TESLA, INC. $2.62B 2025-03-31 TESLA, INC. $595.00M 2025-03-31 TESLA, INC. $447.00M 2025-03-31 TESLA, INC. $109.00M 2025-03-31 APPLE INC $210.33B 2024-03-31 APPLE INC $163.34B 2024-03-31 APPLE INC $115.67B 2024-03-31 APPLE INC $90.75B 2024-03-31 APPLE INC $87.70B 2024-03-31 APPLE INC $66.89B 2024-03-31 APPLE INC $54.52B 2024-03-31 APPLE INC $46.98B 2024-03-31 APPLE INC $45.96B 2024-03-31 APPLE INC $37.27B 2024-03-31 APPLE INC $37.19B 2024-03-31 APPLE INC $24.12B 2024-03-31 APPLE INC $23.87B 2024-03-31 TESLA, INC. $21.30B 2024-03-31 TESLA, INC. $20.71B 2024-03-31 APPLE INC $19.87B 2024-03-31 TESLA, INC. $17.38B 2024-03-31 APPLE INC $16.89B 2024-03-31 TESLA, INC. $16.46B 2024-03-31 APPLE INC $16.37B 2024-03-31 APPLE INC $15.23B 2024-03-31 APPLE INC $14.03B 2024-03-31 APPLE INC $12.58B 2024-03-31 APPLE INC $7.91B 2024-03-31 APPLE INC $7.45B 2024-03-31 APPLE INC $6.72B 2024-03-31 APPLE INC $6.26B 2024-03-31 APPLE INC $5.56B 2024-03-31 TESLA, INC. $2.29B 2024-03-31 TESLA, INC. $1.64B 2024-03-31 TESLA, INC. $1.52B 2024-03-31 TESLA, INC. $476.00M 2024-03-31 TESLA, INC. $442.00M 2024-03-31 TESLA, INC. $113.00M 2024-03-31"""
    ],
    [
        "Database Results Error Only SELECT statements are allowed",
        "RAG Results Tag StockholdersEquity Label Total Stockholders Equity Description Total of all Stockholders Equity items Tag Revenues Label Net Sales Description Total revenue from sale of goods and services Company Apple Inc SIC 3571 EIN None Location None None Tag NetIncomeLoss Label Net Income Description The portion of profit or loss for the period net of income taxes"
    ],
    [
        """Database Results name value ddate APPLE INC $103.14B 2025-03-31 APPLE INC $44.87B 2025-03-31 APPLE INC $97.13B 2024-03-31 APPLE INC $42.27B 2024-03-31""",
        "RAG Results Company Apple Inc SIC 3571 EIN None Location None None Tag NetIncomeLoss Label Net Income Description The portion of profit or loss for the period net of income taxes Tag Revenues Label Net Sales Description Total revenue from sale of goods and services Tag Assets Label Total Assets Description Sum of the carrying amounts as of the balance sheet date of all assets"
    ],
    [
        """Database Results name value ddate MICROSOFT CORP $94.20B 2025-03-31 MICROSOFT CORP $50.78B 2025-03-31 MICROSOFT CORP $32.45B 2025-03-31 MICROSOFT CORP $32.00B 2025-03-31 MICROSOFT CORP $17.38B 2025-03-31 MICROSOFT CORP $11.10B 2025-03-31 MICROSOFT CORP $10.98B 2025-03-31 MICROSOFT CORP $3.53B 2025-03-31 MICROSOFT CORP $81.51B 2024-03-31 MICROSOFT CORP $43.95B 2024-03-31 MICROSOFT CORP $27.98B 2024-03-31 MICROSOFT CORP $27.58B 2024-03-31 MICROSOFT CORP $15.14B 2024-03-31 MICROSOFT CORP $9.57B 2024-03-31 MICROSOFT CORP $9.52B 2024-03-31 MICROSOFT CORP $2.92B 2024-03-31"""
    ],
    [
        """Database Results name value ddate APPLE INC $28.16B 2025-03-31 APPLE INC $25.06B 2025-03-31 APPLE INC $1.97B 2025-03-31 APPLE INC $1.73B 2025-03-31 APPLE INC $1.13B 2025-03-31 APPLE INC $1.13B 2025-03-31 APPLE INC $124.00M 2025-03-31 APPLE INC $66.00M 2025-03-31 APPLE INC $48.00M 2025-03-31 APPLE INC $0.00 2025-03-31 APPLE INC $0.00 2025-03-31 APPLE INC $0.00 2025-03-31 APPLE INC $0.00 2025-03-31 APPLE INC $0.00 2025-03-31 APPLE INC $29.94B 2024-09-30 APPLE INC $27.20B 2024-09-30 APPLE INC $1.97B 2024-09-30 APPLE INC $1.16B 2024-09-30 APPLE INC $778.00M 2024-09-30 APPLE INC $778.00M 2024-09-30 APPLE INC $387.00M 2024-09-30 APPLE INC $212.00M 2024-09-30 APPLE INC $155.00M 2024-09-30 APPLE INC $28.00M 2024-09-30 APPLE INC $26.00M 2024-09-30 APPLE INC $0.00 2024-09-30 APPLE INC $0.00 2024-09-30 APPLE INC $0.00 2024-09-30"""
    ]
]

    # If you prefer, temporarily set use_ground_truth_as_context=True to diagnose faithfulness,
    # but for correct evaluation keep it False (so context must come from your retriever)
    use_ground_truth_as_context = False

    if not queries:
        print("NOTE: queries list is empty. Fill queries, ground_truths, chatbot_answers, and retrieved_contexts_batch before running.")
    else:
        df = evaluate_ragas_batch(queries, ground_truths, chatbot_answers, retrieved_contexts_batch, use_ground_truth_as_context)
        print(df.to_string(index=False))

        # Save results
        now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        excel_filename = f"ragas_evaluations/ragas_evaluation_{now}.xlsx"
        csv_filename = f"ragas_evaluations/ragas_evaluation_{now}.csv"
        df.to_csv(csv_filename, index=False)

        wb = Workbook()
        ws = wb.active
        ws.title = "RAGAS Evaluation"
        headers = list(df.columns)
        ws.append(headers)
        for r in df.itertuples(index=False):
            ws.append(list(r))
        wb.save(excel_filename)
        print(f"Saved {excel_filename} and {csv_filename}")
