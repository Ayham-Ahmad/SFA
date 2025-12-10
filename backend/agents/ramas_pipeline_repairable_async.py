# backend/agents/ramas_pipeline_repairable_async.py
import os
import re
import time
import traceback
import logging
import asyncio
from typing import List, Dict, Tuple, Optional, Any, Callable

# Import core building blocks (expected to exist in your codebase)
from groq import Groq
from backend.agents.planner import plan_task
from backend.agents.ramas_pipeline import (  # re-use helpers from Option B sync file
    extract_steps, normalize_step, validate_and_prepare_steps,
    execute_step_resilient, _dlog, safe_uuid,
)
# from backend.agents.ramas_pipeline_repairable import (  # reuse auditor_v2_validate if present
#     auditor_v2_validate,
# )
from backend.agents.auditor import audit_and_synthesize
from backend.rag_fusion.fusion import rag_fusion_search
from backend.llm import run_chain_of_tables
from backend.security.safety import sanitize_content

# Optional logger helpers
try:
    from backend.d_log import dlog
except Exception:
    dlog = None

try:
    from backend.agent_debug_logger import log_agent_interaction
except Exception:
    def log_agent_interaction(*args, **kwargs):
        return None

# Groq client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_CLIENT = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Logging
logger = logging.getLogger("ramas_pipeline_repairable_async")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(ch)

async def _run_in_executor(func: Callable[..., Any], *args, **kwargs) -> Any:
    """
    Run a synchronous function in the default thread pool executor.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

async def async_plan_task(question: str) -> str:
    return await _run_in_executor(plan_task, question)

async def async_validate_and_prepare_steps(plan_text: str, max_steps: int = 12):
    return await _run_in_executor(validate_and_prepare_steps, plan_text, max_steps)

async def async_execute_step_resilient(normalized_step: str, graph_allowed: bool = False, max_retries: int = 2, retry_delay: float = 1.0) -> Tuple[bool, str]:
    """
    Async wrapper for execute_step_resilient (sync).
    """
    return await _run_in_executor(execute_step_resilient, normalized_step, graph_allowed, max_retries, retry_delay)

async def async_audit_and_synthesize(question: str, context: str, graph_allowed: bool, interaction_id: Optional[str] = None) -> str:
    # audit_and_synthesize might be sync; run in executor
    try:
        return await _run_in_executor(audit_and_synthesize, question, context, graph_allowed, interaction_id=interaction_id)
    except TypeError:
        # try without interaction_id
        return await _run_in_executor(audit_and_synthesize, question, context, graph_allowed)

# Reuse the auditor_v2_validate from the repairable module (it is sync) - wrap it for async use
async def async_auditor_v2_validate(question: str, context: str, graph_allowed: bool, interaction_id: Optional[str] = None) -> Dict:
    return await _run_in_executor(auditor_v2_validate, question, context, graph_allowed, interaction_id)

# Async semaphore-limited concurrent executor for worker steps
async def _execute_steps_concurrently(plan_state: List[Dict],
                                     graph_allowed: bool,
                                     max_concurrency: int = 4) -> None:
    """
    Execute steps whose status is PENDING or FAILED concurrently, limited by max_concurrency.
    This modifies plan_state in-place updating status/result.
    """
    semaphore = asyncio.Semaphore(max_concurrency)
    tasks = []

    async def _exec_one(idx: int, step_obj: Dict):
        async with semaphore:
            _dlog(f"[async] Executing step {idx+1}: {step_obj['normalized'][:200]}")
            try:
                success, result_text = await async_execute_step_resilient(step_obj["normalized"], graph_allowed=graph_allowed)
            except Exception as ex:
                success = False
                result_text = f"Unhandled step execution error: {ex}\n{traceback.format_exc()}"
            step_obj["result"] = result_text
            step_obj["status"] = "OK" if success else "FAILED"
            # Log worker call (non-blocking)
            try:
                # run logging in executor to avoid blocking
                await _run_in_executor(log_agent_interaction, safe_uuid(), "Worker", "Tool Call", step_obj["normalized"], result_text)
            except Exception:
                _dlog("[async] Warning: failed to log worker call.")

    for idx, step_obj in enumerate(plan_state):
        if step_obj["status"] in ("PENDING", "FAILED"):
            tasks.append(asyncio.create_task(_exec_one(idx, step_obj)))

    if tasks:
        await asyncio.gather(*tasks)

# Async repairable pipeline function
async def run_ramas_pipeline_repairable_async(question: str,
                                              max_replans: int = 2,
                                              max_steps_allowed: int = 12,
                                              max_concurrent_workers: int = 4) -> str:
    """
    Async repairable RAMAS pipeline:
      - Uses async wrappers to call sync planner/auditor/worker functions in a threadpool.
      - Executes worker steps concurrently (controlled by max_concurrent_workers).
      - Performs the same replan loop as the sync version, up to max_replans.
    Usage:
      result = await run_ramas_pipeline_repairable_async("Your question here")
    """
    interaction_id = safe_uuid()
    _dlog(f"[{interaction_id}] (async) Starting repairable RAMAS pipeline for: {question[:200]}")

    # Graph authorization
    graph_allowed = False
    if question.strip().startswith("[GRAPH_REQ]"):
        graph_allowed = True
        question = question.replace("[GRAPH_REQ]", "", 1).strip()
        _dlog(f"[{interaction_id}] Graph generation authorized.")

    # Clean log input
    log_input_query = question
    if "User Query:" in question:
        try:
            log_input_query = question.split("User Query:")[-1].strip()
        except Exception:
            pass

    # Log user input (async-safe by delegating to executor)
    try:
        await _run_in_executor(log_agent_interaction, interaction_id, "User", "Input", log_input_query, None)
    except Exception:
        _dlog(f"[{interaction_id}] Warning: failed to log user input.")

    # 1) Initial planning (async wrapper)
    plan_text = await async_plan_task(question)
    _dlog(f"[{interaction_id}] (async) Planner output:\n{plan_text[:1000]}")

    # Validate and normalize
    ok, steps, err = await async_validate_and_prepare_steps(plan_text, max_steps=max_steps_allowed)
    if not ok:
        if steps:
            if isinstance(steps, list) and len(steps) > max_steps_allowed:
                _dlog(f"[{interaction_id}] Planner produced {len(steps)} steps; trimming to {max_steps_allowed}.")
                steps = steps[:max_steps_allowed]
            else:
                return f"Planner output invalid: {err}"
        else:
            return f"Planner output invalid: {err}"

    plan_state = []
    for s in steps:
        plan_state.append({
            "normalized": s,
            "raw": s,
            "status": "PENDING",
            "result": None
        })

    replan_count = 0
    while True:
        # Execute pending/failed steps concurrently
        await _execute_steps_concurrently(plan_state, graph_allowed=graph_allowed, max_concurrency=max_concurrent_workers)

        # Build context for auditor
        context_pieces = []
        for idx, step_obj in enumerate(plan_state):
            context_pieces.append(f"Step: {step_obj['normalized']}\nResult: {step_obj['result'] or ''}")
        context_text = "\n\n".join(context_pieces)

        # Call auditor (async wrapper)
        auditor_response = await async_auditor_v2_validate(question, context_text, graph_allowed, interaction_id=interaction_id)
        _dlog(f"[{interaction_id}] (async) Auditor response: {auditor_response.get('status')} - {auditor_response.get('message')[:300]}")

        # Log auditor output
        try:
            await _run_in_executor(log_agent_interaction, interaction_id, "Auditor", "Validation", context_text, auditor_response.get("synthesized"))
        except Exception:
            _dlog(f"[{interaction_id}] Warning: failed to log auditor output.")

        if auditor_response.get("status") == "OK":
            final_answer = auditor_response.get("synthesized", "")
            try:
                safe_answer = await _run_in_executor(sanitize_content, final_answer)
            except Exception:
                _dlog(f"[{interaction_id}] sanitize_content failed; returning unsanitized answer.")
                safe_answer = final_answer
            _dlog(f"[{interaction_id}] (async) Pipeline completed successfully (no replans needed).")
            return safe_answer

        # Handle REPLAN_REQUIRED
        if auditor_response.get("status") == "REPLAN_REQUIRED":
            replan_indices = auditor_response.get("replan_indices", [])
            replan_msg = auditor_response.get("message", "")
            _dlog(f"[{interaction_id}] (async) Auditor requested replanning for steps: {replan_indices} ; reason: {replan_msg}")

            if replan_count >= max_replans:
                _dlog(f"[{interaction_id}] (async) Max replans reached ({replan_count}). Returning auditor synthesis (best-effort).")
                final_answer = auditor_response.get("synthesized", "")
                try:
                    safe_answer = await _run_in_executor(sanitize_content, final_answer)
                except Exception:
                    safe_answer = final_answer
                return safe_answer

            # Build repair prompt context and call planner async
            repair_prompt_context = (
                f"ORIGINAL QUESTION: {question}\n\n"
                f"AUDITOR_FEEDBACK: {replan_msg}\n"
                f"FAILED_STEP_INDICES: {replan_indices}\n"
                f"CURRENT_PLAN:\n" + "\n".join([f"{i+1}. {p['normalized']}" for i, p in enumerate(plan_state)])
            )

            _dlog(f"[{interaction_id}] (async) Requesting planner to repair steps (replan_count={replan_count+1})...")
            try:
                repaired_plan_text = await async_plan_task(repair_prompt_context)
                _dlog(f"[{interaction_id}] (async) Planner (repair) output:\n{repaired_plan_text[:1000]}")
            except Exception as ex:
                _dlog(f"[{interaction_id}] (async) Planner repair call failed: {ex}")
                for idx in replan_indices:
                    if 0 <= idx < len(plan_state):
                        plan_state[idx]["status"] = "FAILED"
                final_answer = auditor_response.get("synthesized", "")
                try:
                    safe_answer = await _run_in_executor(sanitize_content, final_answer)
                except Exception:
                    safe_answer = final_answer
                return safe_answer

            ok2, repaired_steps, err2 = await async_validate_and_prepare_steps(repaired_plan_text, max_steps=max_steps_allowed)
            if not ok2:
                _dlog(f"[{interaction_id}] (async) Repaired plan validation failed: {err2}. Attempting to salvage.")
                if repaired_steps and isinstance(repaired_steps, list):
                    repaired_steps = repaired_steps[:max_steps_allowed]
                else:
                    final_answer = auditor_response.get("synthesized", "")
                    try:
                        safe_answer = await _run_in_executor(sanitize_content, final_answer)
                    except Exception:
                        safe_answer = final_answer
                    return safe_answer

            # Integrate repaired steps
            if len(repaired_steps) == len(plan_state):
                _dlog(f"[{interaction_id}] (async) Replacing entire plan with repaired plan.")
                plan_state = [{"normalized": s, "raw": s, "status": "PENDING", "result": None} for s in repaired_steps]
            else:
                if len(repaired_steps) == len(replan_indices):
                    for r_idx, step_idx in enumerate(replan_indices):
                        if 0 <= step_idx < len(plan_state):
                            plan_state[step_idx]["normalized"] = repaired_steps[r_idx]
                            plan_state[step_idx]["raw"] = repaired_steps[r_idx]
                            plan_state[step_idx]["status"] = "PENDING"
                            plan_state[step_idx]["result"] = None
                else:
                    _dlog(f"[{interaction_id}] (async) Repaired steps count ({len(repaired_steps)}) doesn't match flagged indices ({len(replan_indices)}). Mapping sequentially.")
                    for i, s in enumerate(repaired_steps):
                        if i < len(replan_indices):
                            step_idx = replan_indices[i]
                            if 0 <= step_idx < len(plan_state):
                                plan_state[step_idx]["normalized"] = s
                                plan_state[step_idx]["raw"] = s
                                plan_state[step_idx]["status"] = "PENDING"
                                plan_state[step_idx]["result"] = None
                        else:
                            if len(plan_state) < max_steps_allowed:
                                plan_state.append({"normalized": s, "raw": s, "status": "PENDING", "result": None})
                            else:
                                _dlog(f"[{interaction_id}] (async) Dropping extra repaired step due to max_steps limit.")
            replan_count += 1
            # loop continues to execute updated pending steps

        # Safety guard: no pending/failed steps but auditor demands replanning
        if not any(p["status"] in ("PENDING", "FAILED") for p in plan_state):
            _dlog(f"[{interaction_id}] (async) No pending/failed steps left but auditor demanded replanning. Returning best-effort synthesis.")
            final_answer = auditor_response.get("synthesized", "")
            try:
                safe_answer = await _run_in_executor(sanitize_content, final_answer)
            except Exception:
                safe_answer = final_answer
            return safe_answer

# Export
__all__ = [
    "run_ramas_pipeline_repairable_async",
]
