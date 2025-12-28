import asyncio
import time
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

# --- Internal Imports ---
from api.db_session import get_db
from api.models import ChatHistory, InteractionType, User
from api.schemas import ChatRequest, ChatFeedbackRequest
from api.auth_utils import get_current_active_user
from backend.pipeline.routing import run_text_query_pipeline
from backend.pipeline.graph_pipeline import run_graph_pipeline
from backend.core.logger import log_user_query, log_system_error, log_system_info
from backend.services.tenant_manager import MultiTenantDBManager

# --- Configuration ---
TIMEOUT_SECONDS = 120.0
CHAT_HISTORY_LIMIT = 2  
router = APIRouter(prefix="/chat", tags=["Chat"])

# --- Global State (Tracking Active Tasks) ---
# We keep track of running queries here so we can cancel them if needed.
active_queries = {}     # Maps query_id -> asyncio Task
query_progress = {}     # Maps query_id -> Status message (e.g., "Reading database...")


# --- Helper Functions ---

def set_query_progress(query_id: str, agent: str, step: str = ""):
    """Updates the status message for the frontend loading bar."""
    query_progress[query_id] = {"agent": agent, "step": step}


def clear_query_progress(query_id: str):
    """Remove progress tracking for completed query."""
    query_progress.pop(query_id, None)


async def run_task_safely(task_func, query_id: str):
    """
    Runs the AI task with a timeout and cancellation support.
    Returns: (text_response, chart_data)
    """
    task = asyncio.create_task(task_func())
    active_queries[query_id] = task

    response_text = ""
    chart_data = None

    try:
        result = await asyncio.wait_for(task, timeout=TIMEOUT_SECONDS)

        if isinstance(result, dict):
            response_text = result.get("message", "")
            if result.get("success"):
                chart_data = result
        else:
            response_text = result

    except asyncio.TimeoutError:
        task.cancel()
        response_text = "Query timed out. Please try a more specific question."
    except asyncio.CancelledError:
        response_text = "Query cancelled by user."
    except Exception as e:
        response_text = f"An error occurred: {str(e)}"
        log_system_error(f"Task Error: {e}")
    finally:
        active_queries.pop(query_id, None)
        clear_query_progress(query_id)

    return response_text, chart_data


# --- Main Endpoints ---

@router.post("")
async def chat_endpoint(
    request: ChatRequest, 
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    """Receives a message, runs the AI, and saves the result."""
    start_time = time.time()
    query_id = request.query_id or str(uuid4())
    
    # 1. Decide if this is a Graph request or a Text request
    is_graph = (request.interaction_type == "graph")
    interaction_type = InteractionType.GRAPH_BUTTON if is_graph else InteractionType.QUERY

    # 2. Build Context (Fetch last 2 messages)
    last_chats = db.query(ChatHistory)\
        .filter(ChatHistory.user_id == current_user.id)\
        .filter(ChatHistory.session_id == request.session_id)\
        .order_by(ChatHistory.timestamp.desc())\
        .limit(CHAT_HISTORY_LIMIT).all()

    # Prepare the input string with history attached
    full_prompt = request.message
    if last_chats and not is_graph:
        history_text = "\n".join([f"Q: {c.question} -> A: {c.answer}" for c in reversed(last_chats)])
        full_prompt = f"Context:\n{history_text}\nUser Query: {request.message}"

    # 3. Define the heavy task (to be run in background)
    set_query_progress(query_id, "planner", "🔍 Analyzing your request...")
    
    async def heavy_ai_task():
        if is_graph:
            return await asyncio.to_thread(run_graph_pipeline, request.message, query_id, current_user)
        else:
            return await asyncio.to_thread(run_text_query_pipeline, full_prompt, query_id, current_user)

    # 4. Run it!
    answer_text, chart_data = await run_task_safely(heavy_ai_task, query_id)

    # 5. Save to Database
    new_chat = ChatHistory(
        user_id=current_user.id,
        session_id=request.session_id,
        question=request.message,
        answer=answer_text,
        interaction_type=interaction_type,
        response_time_seconds=time.time() - start_time
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)  # Ensure ID is populated

    return {
        "response": answer_text,
        "chart_data": chart_data,
        "chat_id": new_chat.id,
        "query_id": query_id
    }


@router.post("/cancel/{query_id}")
async def cancel_query(query_id: str, current_user: User = Depends(get_current_active_user)):
    """Stop a specific query if it's taking too long."""
    if query_id in active_queries:
        active_queries[query_id].cancel()
        return {"status": "cancelled", "query_id": query_id}
    return {"status": "not_found", "query_id": query_id}


@router.get("/status/{query_id}")
async def get_query_status(query_id: str, current_user: User = Depends(get_current_active_user)):
    """Check what the AI is doing right now."""
    if query_id in query_progress:
        return query_progress[query_id]
    return {"agent": "initializing", "step": "⏳ Starting..."}


@router.post("/feedback/{chat_id}")
async def chat_feedback(
    chat_id: int, 
    feedback: str, 
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    """Updates the user feedback (Like/Dislike) for a specific chat message."""
    chat_entry = db.query(ChatHistory).filter(ChatHistory.id == chat_id).first()
    
    if not chat_entry:
        raise HTTPException(status_code=404, detail="Chat entry not found")
        
    if chat_entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    if feedback.lower() == "like":
        chat_entry.user_feedback = 1
    elif feedback.lower() == "dislike":
        chat_entry.user_feedback = 0
    else:
        chat_entry.user_feedback = None
        
    db.commit()
    return {"status": "success", "feedback": chat_entry.user_feedback}

# The chat history that is displayed in the chat window
@router.get("/history")
async def get_chat_history(
    session_id: Optional[str] = None, 
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    """Get previous messages for the current session."""
    if not session_id:
        return []
    
    history = db.query(ChatHistory)\
        .filter(ChatHistory.user_id == current_user.id, ChatHistory.session_id == session_id)\
        .order_by(ChatHistory.timestamp.asc())\
        .all()
    
    return [{
        "id": h.id,
        "question": h.question,
        "answer": h.answer,
        "timestamp": h.timestamp.isoformat(),
        "user_feedback": h.user_feedback
    } for h in history]