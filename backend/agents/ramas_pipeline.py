# backend/agents/ramas_pipeline.py
import os
import re
import time
import uuid
import traceback
import logging
from typing import List, Tuple, Dict, Optional

# External/internal integrations (expected to exist in your project)
from groq import Groq  # existing in your code
from backend.agents.planner import plan_task
from backend.agents.auditor import audit_and_synthesize
from backend.rag_fusion.fusion import rag_fusion_search
from backend.llm import run_chain_of_tables
from backend.security.safety import sanitize_content

# Optional helpers from your repo (used in previous snippets)
try:
    from backend.d_log import dlog
except Exception:
    dlog = None

try:
    from backend.agent_debug_logger import log_agent_interaction
except Exception:
    def log_agent_interaction(*args, **kwargs):
        # fallback no-op if logger missing
        return None

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_CLIENT = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Models (override via env)
CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", "llama-3.1-8b")  # lightweight by default
FALLBACK_CLASSIFIER_MODEL = os.environ.get("FALLBACK_CLASSIFIER_MODEL", "llama-3.3-70b-versatile")
WORKER_MODEL = os.environ.get("WORKER_MODEL", "qwen/qwen3-32b")

# Logging setup
logger = logging.getLogger("ramas_pipeline")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(ch)

# ----------------------
# Utilities
# ----------------------

def _dlog(msg: str):
    if dlog:
        try:
            dlog(msg)
            return
        except Exception:
            pass
    logger.info(msg)

def safe_uuid() -> str:
    return str(uuid.uuid4())

# ----------------------
# Step extraction & normalization
# ----------------------

STEP_SPLIT_PATTERN = re.compile(
    r"""(?mx)                    # multi-line, verbose
    (?:^|\n)                     # start of string or newline
    \s*                          # optional whitespace
    (?:\d+[\.\)]|[-•\*])\s*      # leading numbering '1.' '2)' or bullet '-' '•' '*'
    (?P<step>.+?)                # capture the actual step (non-greedy)
    (?=(?:\n\s*(?:\d+[\.\)]|[-•\*])\s)|\Z)  # until next bullet/number or end
    """
)

INLINE_NUMBERED_SPLIT = re.compile(r"(?<=\d[\.\)])\s+(?=(?:RAG:|SQL:))", re.IGNORECASE)

def extract_steps(plan_text: str) -> List[str]:
    """
    Robust extraction:
    - Handles numbered lines, bullets, inline "1. SQL: ... 2. RAG: ..."
    - Returns list of step strings cleaned (no numbering, no markdown bold)
    """
    if not plan_text or not plan_text.strip():
        return []

    text = plan_text.strip()

    # Handle purely inline steps like "1. SQL: ... 2. RAG: ..."
    # Insert newlines before numeric step markers to split them
    text = re.sub(r"(?<=\d)[\.\)]\s+(?=[A-Za-z])", ".\n", text)

    # Try the robust multi-line pattern first
    matches = list(STEP_SPLIT_PATTERN.finditer(text))
    steps = []
    if matches:
        for m in matches:
            s = m.group("step").strip()
            steps.append(s)
    else:
        # Fallback: split by newlines and treat lines that look like steps
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # remove leading numbering or bullets
            line = re.sub(r"^\s*(?:\d+[\.\)]|[-•\*])\s*", "", line)
            steps.append(line)

    # Final cleanup for each step
    cleaned = []
    for s in steps:
        # remove markdown bold/italic etc.
        s = re.sub(r"[*_`]+", "", s)
        s = s.strip()
        if s:
            cleaned.append(s)
    return cleaned

def normalize_step(step: str) -> str:
    """
    Normalize a single step so it starts with 'SQL:' or 'RAG:' (uppercase)
    If unspecified, try to infer:
      - If the step contains SQL keywords (SELECT, FROM, WHERE, JOIN), prefer SQL
      - Otherwise default to RAG.
    Also remove leading labels like 'Step 1:' or '1.' if present.
    """
    s = step.strip()

    # Remove leading numbering like "Step 1:", "1)", "1."
    s = re.sub(r"^\s*(?:Step\s*)?\d+[\.\)]\s*", "", s, flags=re.IGNORECASE)
    s = s.strip()

    # If step already contains SQL: or RAG:, normalize capitalization
    if re.match(r'^(SQL|RAG)\s*:', s, re.IGNORECASE):
        kind, rest = re.split(r'\s*:\s*', s, maxsplit=1)
        return f"{kind.strip().upper()}: {rest.strip()}"

    # Heuristic: detect SQL-like text
    if re.search(r'\b(SELECT|FROM|WHERE|JOIN|GROUP BY|ORDER BY|LIMIT|COUNT|SUM|AVG)\b', s, re.IGNORECASE):
        return f"SQL: {s}"
    # If looks like a short instruction that references a doc/definition -> RAG
    return f"RAG: {s}"

# ----------------------
# Resilient worker executor
# ----------------------

def execute_step_resilient(step: str,
                           graph_allowed: bool = False,
                           max_retries: int = 2,
                           retry_delay: float = 1.0) -> Tuple[bool, str]:
    """
    Executes a single normalized step.
    Returns (success, result_text).
    Respects graph_allowed and retries transient errors.
    """
    step = step.strip()
    if not step:
        return False, "Empty step"

    # Normalize prefix detection safely
    m = re.match(r'^(SQL|RAG)\s*:\s*(.*)$', step, flags=re.IGNORECASE)
    if not m:
        return False, f"Unknown tool in step: {step}"

    tool = m.group(1).upper()
    query = m.group(2).strip()

    last_err = None
    for attempt in range(1, max_retries + 2):
        try:
            if tool == "RAG":
                _dlog(f"Worker executing RAG (attempt {attempt}): {query[:200]}...")
                # Use a small n_results by default; allow caller to include preference in query text if wanted
                results = rag_fusion_search(query, n_results=3)
                # Create short sanitized result. If result items may include long content, truncate for logs only.
                res_text = "\n".join([f"- {r.get('content', '')}" for r in results])
                return True, f"RAG Results for '{query}':\n{res_text}"

            elif tool == "SQL":
                _dlog(f"Worker executing SQL (attempt {attempt}): {query[:200]}...")
                # If graph generation is requested and the step mentions a time series or 'trend', we could flag it.
                # We'll simply pass graph_allowed to the SQL runner via model argument or context if needed.
                # Here we call run_chain_of_tables (assumed to return a string).
                result = run_chain_of_tables(query, model=WORKER_MODEL, graph_allowed=graph_allowed) \
                         if 'graph_allowed' in run_chain_of_tables.__code__.co_varnames \
                         else run_chain_of_tables(query, model=WORKER_MODEL)
                return True, f"SQL Execution Result for '{query}':\n{result}"
            else:
                return False, f"Unsupported tool '{tool}' in step: {step}"

        except Exception as ex:
            last_err = ex
            _dlog(f"Worker error (attempt {attempt}) for step '{step}': {ex}")
            if attempt <= max_retries:
                time.sleep(retry_delay * attempt)
                continue
            else:
                err_trace = traceback.format_exc()
                return False, f"Error executing step after {attempt} attempts: {str(ex)}\n{err_trace}"

    return False, f"Unhandled worker failure for step: {step}"

# ----------------------
# Planner output validator
# ----------------------

def validate_and_prepare_steps(plan_text: str,
                               max_steps: int = 12) -> Tuple[bool, List[str], Optional[str]]:
    """
    Validates planner output and returns normalized steps.
    Returns (ok, steps, error_message)
    """
    if not plan_text or not plan_text.strip():
        return False, [], "Planner returned empty plan"

    raw_steps = extract_steps(plan_text)
    if not raw_steps:
        # Try fallback: split by lines and take non-empty lines
        raw_steps = [line.strip() for line in plan_text.splitlines() if line.strip()]

    normalized = [normalize_step(s) for s in raw_steps if s.strip()]
    if not normalized:
        return False, [], "No actionable steps found in planner output"

    if len(normalized) > max_steps:
        return False, normalized, f"Planner returned too many steps ({len(normalized)}). Max allowed is {max_steps}."

    # Ensure each step uses allowed tools
    for s in normalized:
        if not re.match(r'^(SQL|RAG)\s*:\s*.+', s, re.IGNORECASE):
            return False, normalized, f"Invalid step format (must start with SQL: or RAG:): '{s}'"

    return True, normalized, None

# ----------------------
# Intent classifier (lightweight with fallback)
# ----------------------

def classify_intent(user_text: str) -> str:
    """
    Return 'CONVERSATIONAL' or 'ANALYTICAL'.
    We use a lightweight model first (CLASSIFIER_MODEL). If the call fails, fallback to heavier model.
    If Groq client isn't available, default to ANALYTICAL for safety.
    """
    prompt = f"""
    Classify the following user input into two categories:
    1. CONVERSATIONAL: Greetings, small talk, questions about identity.
    2. ANALYTICAL: Questions requiring data, numbers, financial info, companies, or database lookup.

    Input: {user_text}

    Return ONLY one word: CONVERSATIONAL or ANALYTICAL.
    """

    client = GROQ_CLIENT
    if not client:
        # No client - default to analytical to allow pipeline to continue
        _dlog("GROQ client not configured; defaulting intent to ANALYTICAL.")
        return "ANALYTICAL"

    # Try lightweight classifier model first
    for model in (CLASSIFIER_MODEL, FALLBACK_CLASSIFIER_MODEL):
        try:
            resp = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0,
                max_tokens=8
            )
            classification = resp.choices[0].message.content.strip().upper()
            if "CONVERSATIONAL" in classification:
                return "CONVERSATIONAL"
            else:
                return "ANALYTICAL"
        except Exception as ex:
            _dlog(f"Classifier model {model} failed: {ex}")
            continue

    # As a last resort:
    return "ANALYTICAL"

# ----------------------
# Main RAMAS Orchestration (Production-grade)
# ----------------------

def run_ramas_pipeline(question: str) -> str:
    """
    Full production-grade RAMAS orchestration.
    Steps:
      - Parse graph authorization flag
      - Clean and log input
      - Intent classification (lightweight -> heavy fallback)
      - If conversational: handle via small chatflow
      - If analytical: use planner -> validate steps -> execute steps resiliently -> audit -> sanitize -> return
    """
    interaction_id = safe_uuid()
    _dlog(f"--- Starting RAMAS Pipeline [{interaction_id}] for: {question[:200]} ---")

    # 0. Graph authorization flag
    graph_allowed = False
    if question.strip().startswith("[GRAPH_REQ]"):
        graph_allowed = True
        question = question.replace("[GRAPH_REQ]", "", 1).strip()
        _dlog(f"[{interaction_id}] Graph generation authorized by user request.")

    # 0b. Extract cleaned user query for logs (if the input contains "User Query:")
    log_input_query = question
    if "User Query:" in question:
        try:
            log_input_query = question.split("User Query:")[-1].strip()
        except Exception:
            _dlog(f"[{interaction_id}] Failed to parse 'User Query:' - using full input for logging.")

    # Log user input
    try:
        log_agent_interaction(interaction_id, "User", "Input", log_input_query, None)
    except Exception:
        _dlog(f"[{interaction_id}] Warning: failed to log user input via agent logger.")

    # 1. Intent classification
    intent = "ANALYTICAL"
    try:
        intent = classify_intent(log_input_query)
        _dlog(f"[{interaction_id}] Intent classified as: {intent}")
    except Exception as ex:
        _dlog(f"[{interaction_id}] Intent classification failed: {ex}. Defaulting to ANALYTICAL.")

    # If conversational -> shortcut chat path
    if intent == "CONVERSATIONAL":
        _dlog(f"[{interaction_id}] Routing to conversational agent.")
        try:
            # Use the heavy model or a chat model: reuse GROQ client or fallback
            if GROQ_CLIENT:
                chat_prompt = f"You are a helpful Financial AI Assistant. User says: \"{log_input_query}\" Reply concisely and professionally."
                resp = GROQ_CLIENT.chat.completions.create(
                    messages=[{"role": "user", "content": chat_prompt}],
                    model=FALLBACK_CLASSIFIER_MODEL,
                    temperature=0.2,
                    max_tokens=300
                )
                reply = resp.choices[0].message.content.strip()
            else:
                reply = "Hello! How can I assist you today?"

            # Log and return
            try:
                log_agent_interaction(interaction_id, "ConversationalAgent", "Output", log_input_query, reply)
            except Exception:
                _dlog(f"[{interaction_id}] Warning: failed to log conversational output.")
            return reply

        except Exception as ex:
            _dlog(f"[{interaction_id}] Conversational path failed: {ex}")
            return "Hello! How can I assist you today?"

    # 2. Planner path (ANALYTICAL)
    try:
        _dlog(f"[{interaction_id}] Calling planner...")
        plan = plan_task(question)
        _dlog(f"[{interaction_id}] Planner returned:\n{plan}")

        # Log the planner output
        try:
            log_agent_interaction(interaction_id, "Planner", "Output", log_input_query, plan)
        except Exception:
            _dlog(f"[{interaction_id}] Warning: failed to log planner output.")

        # Validate and normalize steps
        ok, steps, err = validate_and_prepare_steps(plan, max_steps=12)
        if not ok:
            # If we have steps but too many, still attempt to continue but cap.
            if steps:
                # If steps > max, trim and continue; otherwise abort.
                if isinstance(steps, list) and len(steps) > 12:
                    _dlog(f"[{interaction_id}] Trimming planner steps from {len(steps)} to 12.")
                    steps = steps[:12]
                else:
                    _dlog(f"[{interaction_id}] Planner validation failed: {err}")
                    return f"Planner output invalid: {err}"
            else:
                _dlog(f"[{interaction_id}] Planner validation failed: {err}")
                return f"Planner output invalid: {err}"

        # 3. Worker loop
        context_pieces: List[str] = []
        for idx, raw_step in enumerate(steps, start=1):
            _dlog(f"[{interaction_id}] Preparing to execute step {idx}: {raw_step[:200]}")
            try:
                success, result = execute_step_resilient(raw_step, graph_allowed=graph_allowed)
            except Exception as ex:
                success = False
                result = f"Unhandled error executing step: {ex}\n{traceback.format_exc()}"

            # Short logging summary
            _dlog(f"[{interaction_id}] Step {idx} {'succeeded' if success else 'failed'}: {result[:300]}")

            # Append to context used by auditor
            context_pieces.append(f"Step: {raw_step}\nResult: {result}")

            # Log worker tool call
            try:
                log_agent_interaction(interaction_id, "Worker", "Tool Call", raw_step, result)
            except Exception:
                _dlog(f"[{interaction_id}] Warning: failed to log worker call for step {idx}.")

        context_text = "\n\n".join(context_pieces)

        # 4. Audit & synthesize
        _dlog(f"[{interaction_id}] Auditing and synthesizing answer...")
        try:
            final_answer = audit_and_synthesize(question, context_text, graph_allowed, interaction_id=interaction_id)
        except TypeError:
            # Some auditor signatures may not accept interaction_id or graph_allowed; attempt fallback call
            try:
                final_answer = audit_and_synthesize(question, context_text, graph_allowed)
            except Exception as ex2:
                _dlog(f"[{interaction_id}] Auditor failure: {ex2}")
                return f"Error during auditing: {ex2}"

        # Log Auditor output (pre-safety)
        try:
            log_agent_interaction(interaction_id, "Auditor", "Output", context_text, final_answer)
        except Exception:
            _dlog(f"[{interaction_id}] Warning: failed to log auditor output.")

        # 5. Safety guard / sanitize
        try:
            safe_answer = sanitize_content(final_answer)
        except Exception as ex:
            _dlog(f"[{interaction_id}] sanitize_content failed: {ex}. Returning unsanitized auditor result.")
            safe_answer = final_answer

        _dlog(f"[{interaction_id}] Pipeline completed successfully.")
        return safe_answer

    except Exception as pipeline_ex:
        err = traceback.format_exc()
        _dlog(f"[{interaction_id}] Fatal pipeline error: {err}")
        # Try to log pipeline error
        try:
            log_agent_interaction(interaction_id, "Pipeline", "Error", question, err)
        except Exception:
            _dlog(f"[{interaction_id}] Warning: failed to log pipeline error.")
        return f"Error encountered in pipeline: {str(pipeline_ex)[:300]}"

# Optional: expose helper functions for testing
__all__ = [
    "run_ramas_pipeline",
    "extract_steps",
    "normalize_step",
    "execute_step_resilient",
    "validate_and_prepare_steps",
]
