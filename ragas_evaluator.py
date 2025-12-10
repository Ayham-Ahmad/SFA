"""
Full RAGAS-style Evaluation Pipeline
- Dimensions: Faithfulness, Answer Relevance, Context Recall, Context Precision, Answer Correctness
- Uses embeddings (sentence-transformers) for semantic similarity
- Uses spaCy for entity extraction
- Uses rapidfuzz for fuzzy matching
- Numeric extraction and mapping numbers to specific entities (company-level)
- Save detailed results to Excel/CSV

Dependencies:
    pip install sentence-transformers==2.2.2 spacy==3.5.4 openpyxl rapidfuzz pandas numpy python-dateutil

Optional (for better NER models):
    python -m spacy download en_core_web_trf   # transformer-based NER (big)
    or
    python -m spacy download en_core_web_sm    # smaller

Notes:
- Provide `queries`, `ground_truths`, `chatbot_answers`, and `retrieved_contexts` lists aligned by index.
- retrieved_contexts: list of strings OR list of lists of strings (top-k context passages).
"""

import re
import math
import json
from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import spacy
from rapidfuzz import fuzz, process
from openpyxl import Workbook
from datetime import datetime
from dateutil.parser import parse as parse_date

# ----------------------------
# CONFIG
# ----------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # fast + accurate for semantic similarity
SIM_THRESHOLD = 0.70                 # cosine similarity threshold for 'close'
NUM_TOLERANCE = 0.10                 # relative tolerance for numeric equality (10%)
TOPK_CONTEXT = 5                     # assume up to top-k retrieved contexts
RAGAS_WEIGHTS = {
    "faithfulness": 0.25,
    "answer_relevance": 0.20,
    "context_recall": 0.20,
    "context_precision": 0.10,
    "answer_correctness": 0.25
}

# ----------------------------
# LOAD MODELS
# ----------------------------
print("Loading models...")
embedder = SentenceTransformer(EMBEDDING_MODEL)
try:
    nlp = spacy.load("en_core_web_sm")
except Exception:
    # fallback if model not present
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")
print("Models loaded.")

# ----------------------------
# UTILITIES: numeric extraction + normalization
# ----------------------------
def extract_numeric_expressions(text: str) -> List[Tuple[float, str]]:
    """
    Returns list of (value_in_float, original_unit_str) found in text.
    Handles patterns like: $219.66B, 219.66 B, 219,660,000,000, $29.94 Billion, 29.94bn
    """
    if not text:
        return []
    text_u = text.upper().replace(',', '')
    results = []
    # common patterns
    # $219.66B or 219.66B or 219.66 BN
    for m in re.finditer(r'\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(B|BN|BILLION|M|MN|MILLION|K|THOUSAND)?', text_u):
        num_str = m.group(1)
        unit = m.group(2) or ''
        try:
            val = float(num_str)
        except:
            continue
        unit = unit.strip()
        if unit in ('B','BN','BILLION'):
            val *= 1e9
        elif unit in ('M','MN','MILLION'):
            val *= 1e6
        elif unit in ('K','THOUSAND'):
            val *= 1e3
        # If no unit specified but very large (>= 1e9) maybe already absolute; keep as-is.
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
    """Return list of PERSON/ORG/GPE entities (lowercased)."""
    if not text:
        return []
    doc = nlp(str(text))
    ents = [ent.text.lower() for ent in doc.ents if ent.label_ in ("ORG","PERSON","GPE","PRODUCT")]
    # include simple heuristics for company names like "Apple", "Microsoft"
    # fallback: extract capitalized words (single-token) not at beginning of sentence
    if not ents:
        caps = re.findall(r'\b([A-Z][a-zA-Z0-9&\.\-]{1,30})\b', text)
        ents = [c.lower() for c in caps]
    # deduplicate
    seen = set()
    out = []
    for e in ents:
        if e in seen: continue
        seen.add(e)
        out.append(e)
    return out

def map_numbers_to_entities(text: str) -> Dict[str, List[float]]:
    """
    Very pragmatic mapping:
    - If text contains a known entity and a number nearby, map that number to entity.
    - We'll use simple window: sentence-level proximity using regex split.
    Returns dict: {entity_name: [numbers]}
    """
    out = {}
    if not text:
        return out
    sentences = re.split(r'[.;]\s*', text)
    for sent in sentences:
        ents = extract_entities(sent)
        nums = [v for (v,u) in extract_numeric_expressions(sent)]
        if ents and nums:
            for e in ents:
                out.setdefault(e, []).extend(nums)
        else:
            # if no entity but single number and a known company name exists anywhere in the full text
            nums_all = [v for (v,u) in extract_numeric_expressions(sent)]
            if nums_all:
                # try to find nearest capitalized token in the full text
                caps = re.findall(r'\b([A-Z][a-zA-Z0-9&\.\-]{1,30})\b', text)
                if caps:
                    ent = caps[0].lower()
                    out.setdefault(ent, []).extend(nums_all)
    return out

# ----------------------------
# SEMANTIC SIMILARITY (embedding)
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
    """
    Does answer address the query? (embedding similarity + keyword overlap)
    """
    sim = semantic_similarity(query, answer)
    # keyword overlap heuristic
    q_words = set(re.findall(r'\w+', query.lower()))
    a_words = set(re.findall(r'\w+', answer.lower()))
    overlap = len(q_words & a_words) / (len(q_words) + 1e-9)
    return 0.6 * sim + 0.4 * overlap

def score_answer_correctness(gt: str, answer: str) -> float:
    """
    Combines:
      - Numeric matching (entity-aware)
      - Semantic similarity (embeddings)
      - Fuzzy textual match
    """
    # semantic
    sem = semantic_similarity(gt, answer)

    # fuzzy textual match
    fuzzy = fuzz.token_sort_ratio(str(gt), str(answer)) / 100.0

    # numeric: compare matched entity numbers
    gt_map = map_numbers_to_entities(gt)
    cb_map = map_numbers_to_entities(answer)
    # if ground truth has numeric values, compare per-entity
    if gt_map:
        entity_scores = []
        for ent, gt_vals in gt_map.items():
            # attempt match by fuzzy name to cb_map keys
            best_match = None
            best_ratio = 0
            for cb_ent in cb_map:
                r = fuzz.token_sort_ratio(ent, cb_ent)
                if r > best_ratio:
                    best_ratio = r
                    best_match = cb_ent
            if best_match and best_ratio >= 60:
                # compare first numbers or all numbers
                cb_vals = cb_map.get(best_match, [])
                # compare closest pair
                best_val_score = 0.0
                for g in gt_vals:
                    for c in cb_vals:
                        if max(g,c) == 0:
                            ratio = 0
                        else:
                            ratio = min(g,c) / max(g,c)
                        # convert ratio to score: if within NUM_TOLERANCE -> 1, else scaled by ratio
                        if ratio >= (1 - NUM_TOLERANCE):
                            score = 1.0
                        else:
                            score = ratio
                        if score > best_val_score:
                            best_val_score = score
                entity_scores.append(best_val_score)
            else:
                # entity not found in cb -> zero for numeric
                entity_scores.append(0.0)
        num_score = sum(entity_scores) / len(entity_scores) if entity_scores else 0.0
    else:
        # no numeric GT; if embeddings/fuzzy good, consider it correct
        num_score = 1.0 if not extract_numeric_expressions(answer) else 0.5

    # aggregate: weighted
    return 0.5 * sem + 0.2 * fuzzy + 0.3 * num_score

def score_context_recall(answer: str, retrieved_contexts: List[str]) -> float:
    """
    Does the retrieved context contain the facts used in the answer?
    We'll measure maximum semantic similarity between answer and each context,
    plus whether numeric facts in answer appear verbatim or as numbers inside contexts.
    """
    if not retrieved_contexts:
        return 0.0
    sims = [semantic_similarity(answer, c) for c in retrieved_contexts]
    sim_score = max(sims) if sims else 0.0

    # numeric coverage: ensure answer's numbers appear in contexts
    answer_nums = [v for (v,u) in extract_numeric_expressions(answer)]
    if not answer_nums:
        num_cov = 1.0  # nothing to cover
    else:
        found = 0
        total = len(answer_nums)
        for an in answer_nums:
            matched = False
            for c in retrieved_contexts:
                for (v,u) in extract_numeric_expressions(c):
                    ratio = min(v, an) / max(v, an) if max(v, an) > 0 else 0
                    if ratio >= (1 - NUM_TOLERANCE):
                        matched = True
                        break
                if matched: break
            if matched: found += 1
        num_cov = found / total
    return 0.7 * sim_score + 0.3 * num_cov

def score_context_precision(answer: str, retrieved_contexts: List[str]) -> float:
    """
    What fraction of the retrieved context is actually used to answer?
    Heuristic: compute semantic similarity between each context and the answer,
    then weight by how much each context's content overlaps (top contexts used).
    If contexts are long, measure token overlap ratio.
    """
    if not retrieved_contexts:
        return 0.0
    sims = [semantic_similarity(answer, c) for c in retrieved_contexts]
    # normalize sims into a 0-1 distribution and treat top-k as used
    arr = np.array(sims)
    if arr.sum() == 0:
        return 0.0
    probs = arr / arr.sum()
    # context precision = sum of probs for contexts with sim > SIM_THRESHOLD/2 (used contexts)
    used_mask = arr >= (SIM_THRESHOLD * 0.5)
    precision = probs[used_mask].sum()
    return float(precision)

def score_faithfulness(answer: str, retrieved_contexts: List[str]) -> float:
    """
    Faithfulness: are claims in the answer supported by the retrieved context?
    We'll extract named claims (entities + numbers + dates) and check presence.
    """
    # strategy: sentences in answer -> check if each sentence has supporting context with sim >= SIM_THRESHOLD
    if not answer:
        return 0.0
    sentences = [s.strip() for s in re.split(r'[.;]\s*', answer) if s.strip()]
    if not sentences:
        return 0.0
    supp_count = 0
    for s in sentences:
        sims = [semantic_similarity(s, c) for c in retrieved_contexts] if retrieved_contexts else [0.0]
        best = max(sims) if sims else 0.0
        # also check numeric support if sentence contains numbers
        s_nums = [v for (v,u) in extract_numeric_expressions(s)]
        numeric_ok = True
        if s_nums:
            numeric_ok = False
            for c in retrieved_contexts:
                for (v,u) in extract_numeric_expressions(c):
                    for s_n in s_nums:
                        ratio = min(v, s_n) / max(v, s_n) if max(v, s_n) > 0 else 0
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
def evaluate_ragas_batch(queries: List[str],
                         ground_truths: List[str],
                         chatbot_answers: List[str],
                         retrieved_contexts_batch: List[List[str]] = None) -> pd.DataFrame:
    """
    retrieved_contexts_batch: list aligned with queries; each item is list of retrieved passages (strings)
    If None, we use empty contexts.
    """
    n = len(queries)
    if not retrieved_contexts_batch:
        retrieved_contexts_batch = [[] for _ in range(n)]
    rows = []
    for i, (q, gt, cb, contexts) in enumerate(zip(queries, ground_truths, chatbot_answers, retrieved_contexts_batch)):
        ans_rel = score_answer_relevance(q, cb)
        ans_corr = score_answer_correctness(gt, cb)
        ctx_recall = score_context_recall(cb, contexts)
        ctx_prec = score_context_precision(cb, contexts)
        faith = score_faithfulness(cb, contexts)

        # Compose final RAGAS-like overall score using configured weights
        overall = (RAGAS_WEIGHTS['faithfulness'] * faith +
                   RAGAS_WEIGHTS['answer_relevance'] * ans_rel +
                   RAGAS_WEIGHTS['context_recall'] * ctx_recall +
                   RAGAS_WEIGHTS['context_precision'] * ctx_prec +
                   RAGAS_WEIGHTS['answer_correctness'] * ans_corr)

        # Categorize PASS/FAIL with threshold
        pass_fail = "PASS" if overall >= 0.65 else "FAIL"

        rows.append({
            "index": i+1,
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
# Example usage with your provided lists
# ----------------------------
if __name__ == "__main__":
    # Replace these with your actual lists; example uses the lists from your original script
    queries = [
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
    ground_truth = [
        "Apple Inc revenue (2025-03-31): $219.66B",
        "Microsoft Corp revenue (2025-03-31): $205.28B",
        "Apple: $219.66B, Microsoft: $205.28B. Apple has higher revenue.",
        "Apple Inc net income (2025-03-31): $93.74B",
        "Microsoft Corp total assets: $512.16B",
        "Apple: $219.66B, Tesla: $97.69B",
        "Should return list of top 5 companies sorted by revenue value descending",
        "Apple Inc gross profit: $92.96B",
        "Microsoft Corp operating income: $94.20B",
        "Apple Inc cash: $29.94B"
    ]
    chatbot_answers = [
        "Apple $219.66B 2025-03-31",
        "Microsoft $205.28B 2025-03-31",
        "Apple's revenue for 2025: $219.66B. Microsoft's revenue for 2025: $205.28B.",
        "Apple's net income for 2025: $61.11B.",
        "Microsoft's total assets as of March 31, 2025: $562.62B.",
        "Apple's revenue for 2025: $219.66B. Tesla's revenue for 2025: $19.34B.",
        "Data not available for this query.",
        "Apple's gross profit for 2025: $103.14B.",
        "MICROSOFT CORP $94.20B 2025-03-31",
        "Apple's cash and equivalents for 2025-03-31: $28.16B.",
    ]
    # Example retrieved contexts (for faithfulness/context scoring) - ideally this is what your retriever returned
    retrieved_contexts_batch = [
        ["Apple Inc. reported revenue of $219.66B for FY 2025, quarter ended 2025-03-31."],
        ["Microsoft Corp reported revenue $205.28B for FY2025, quarter ended 2025-03-31."],
        ["Apple revenue $219.66B; Microsoft revenue $205.28B. Apple higher than Microsoft."],
        ["Apple net income $93.74B as of 2025-03-31 per Apple filing."],
        ["Microsoft total assets $512.16B as of 2025-03-31 (balance sheet)."],
        ["Apple revenue $219.66B; Tesla revenue $97.69B (FY2025)."],
        ["Top companies by revenue: Walmart, Amazon, State Grid, China National Petroleum, Sinopec (example)"],
        ["Apple gross profit $92.96B per FY2025 results."],
        ["Microsoft operating income $94.20B per FY2025."],
        ["Apple cash and equivalents $29.94B as of 2025-03-31."]
    ]

    df = evaluate_ragas_batch(queries, ground_truth, chatbot_answers, retrieved_contexts_batch)
    print(df.to_string(index=False))

    # Save to Excel and CSV
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    excel_filename = f"ragas_evaluation_{now}.xlsx"
    csv_filename = f"ragas_evaluation_{now}.csv"
    df.to_csv(csv_filename, index=False)

    # For Excel with some formatting:
    wb = Workbook()
    ws = wb.active
    ws.title = "RAGAS Evaluation"
    headers = list(df.columns)
    ws.append(headers)
    for r in df.itertuples(index=False):
        ws.append(list(r))
    wb.save(excel_filename)
    print(f"Saved {excel_filename} and {csv_filename}")
