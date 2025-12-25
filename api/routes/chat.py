"""
Chat Routes
============
Handles AI chat, query management, and chat history.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import asyncio
from asyncio import CancelledError
from uuid import uuid4
import time

from api.database import get_db
from api.models import User, ChatHistory, InteractionType
from api.schemas import ChatRequest
from api.auth import get_current_active_user
from backend.routing import run_ramas_pipeline
from backend.sfa_logger import log_system_error

router = APIRouter(prefix="/chat", tags=["Chat"])

# Global dictionaries for query tracking (shared with main app)
active_queries = {}
query_progress = {}


def _log_cancellation(query_id: str, question: str, reason: str):
    """Log query cancellations to debug file."""
    from datetime import datetime
    import json
    import os
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query_id": query_id,
        "question": question[:100],
        "reason": reason
    }
    debug_path = "debug/cancellations.json"
    os.makedirs("debug", exist_ok=True)
    
    logs = []
    if os.path.exists(debug_path):
        try:
            with open(debug_path, "r") as f:
                logs = json.load(f)
        except Exception:
            logs = []
    
    logs.append(log_entry)
    with open(debug_path, "w") as f:
        json.dump(logs[-100:], f, indent=2)


def set_query_progress(query_id: str, agent: str, step: str = ""):
    """Update progress status for a query."""
    query_progress[query_id] = {"agent": agent, "step": step}


def clear_query_progress(query_id: str):
    """Remove progress tracking for completed query."""
    query_progress.pop(query_id, None)


@router.post("")
async def chat_endpoint(
    request: ChatRequest, 
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    """
    Main endpoint for interacting with the AI Financial Advisor.
    Handles message history context, RAG pipeline execution, and storing history.
    
    For graph requests (interaction_type='graph'), uses dedicated graph pipeline
    that builds charts programmatically without LLM involvement.
    """
    start_time = time.time()
    query_id = request.query_id if request.query_id else str(uuid4())
    
    # 1. Determine Interaction Type
    itype = InteractionType.QUERY
    is_graph_request = request.interaction_type == "graph"
    if is_graph_request:
        itype = InteractionType.GRAPH_BUTTON

    # 2. Retrieve Chat History for Context
    query_builder = db.query(ChatHistory).filter(ChatHistory.user_id == current_user.id)
    
    if request.session_id:
         query_builder = query_builder.filter(ChatHistory.session_id == request.session_id)
         
    last_exchanges = query_builder.order_by(ChatHistory.timestamp.desc()).limit(2).all()

    full_context_query = request.message
    
    # 3. Inject Context
    if last_exchanges:
        history_lines = []
        for ex in reversed(last_exchanges):
            answer_clean = ex.answer.split("graph_data||")[0].strip() if "graph_data||" in ex.answer else ex.answer
            history_lines.append(f"Q: {ex.question} -> A: {answer_clean}")
        
        context_str = "\n".join(history_lines)
        full_context_query = f"Context:\n{context_str}\nUser Query: {request.message}"
    
    # 4. Execute the appropriate pipeline
    response_text = ""
    chart_data = None
    
    try:
        set_query_progress(query_id, "planner", "Analyzing question...")
        
        if is_graph_request:
            # Use NEW clean graph pipeline (returns raw data, frontend renders)
            from backend.graph_pipeline import run_graph_pipeline
            
            async def run_graph_task():
                return await asyncio.to_thread(run_graph_pipeline, request.message, query_id)
            
            task = asyncio.create_task(run_graph_task())
            active_queries[query_id] = task
            
            try:
                result = await asyncio.wait_for(task, timeout=120.0)
                response_text = result.get("message", "")
                
                if result.get("success"):
                    chart_data = {
                        "chart_type": result.get("chart_type"),
                        "labels": result.get("labels"),
                        "values": result.get("values"),
                        "title": result.get("title"),
                        "is_percentage": result.get("is_percentage", False),
                        "y_axis_title": result.get("y_axis_title", "USD")
                    }
                    
            except asyncio.TimeoutError:
                task.cancel()
                response_text = "Query timed out. Please try a simpler question."
                _log_cancellation(query_id, request.message, "timeout")
            except CancelledError:
                response_text = "Query cancelled by user."
                _log_cancellation(query_id, request.message, "user_cancelled")
            finally:
                active_queries.pop(query_id, None)
                clear_query_progress(query_id)
        else:
            # Use standard RAMAS pipeline for text responses
            async def run_text_task():
                return await asyncio.to_thread(run_ramas_pipeline, full_context_query, query_id)
            
            task = asyncio.create_task(run_text_task())
            active_queries[query_id] = task
            
            try:
                response_text = await asyncio.wait_for(task, timeout=120.0)
            except asyncio.TimeoutError:
                task.cancel()
                response_text = "Query timed out after 2 minutes. Please try a more specific question."
                _log_cancellation(query_id, request.message, "timeout")
            except CancelledError:
                response_text = "Query cancelled by user."
                _log_cancellation(query_id, request.message, "user_cancelled")
            finally:
                active_queries.pop(query_id, None)
                clear_query_progress(query_id)
    
    except Exception as e:
        response_text = f"An error occurred: {str(e)}"
        log_system_error(f"Chat Endpoint Error: {e}")
    
    # Measure processing time
    end_time = time.time()
    duration = end_time - start_time
    
    # 5. Persist the interaction to the database
    new_history = ChatHistory(
        user_id=current_user.id,
        session_id=request.session_id,
        question=request.message,
        answer=response_text,
        interaction_type=itype,
        response_time_seconds=duration,
        user_feedback=None
    )
    db.add(new_history)
    db.commit()
    db.refresh(new_history)
    
    # 6. Return structured response
    return {
        "response": response_text,
        "chart_data": chart_data,
        "chat_id": new_history.id,
        "query_id": query_id
    }


@router.post("/cancel/{query_id}")
async def cancel_query(query_id: str, current_user: User = Depends(get_current_active_user)):
    """Cancel a running query by its query_id."""
    if query_id in active_queries:
        active_queries[query_id].cancel()
        return {"status": "cancelled", "query_id": query_id}
    return {"status": "not_found", "query_id": query_id}


@router.get("/status/{query_id}")
async def get_query_status(query_id: str, current_user: User = Depends(get_current_active_user)):
    """Get the current status of a running query (for progress indicator)."""
    if query_id in query_progress:
        return query_progress[query_id]
    return {"status": "unknown", "agent": "initializing"}


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


@router.get("/history")
async def get_chat_history(
    session_id: str = None, 
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    """
    Retrieve the chat history for the current user's specific session.
    If session_id is provided, returns only messages from that session.
    If session_id is not provided or has no messages, returns empty list.
    """
    if not session_id:
        return []
    
    history = db.query(ChatHistory).filter(
        ChatHistory.user_id == current_user.id,
        ChatHistory.session_id == session_id
    ).order_by(ChatHistory.timestamp.asc()).all()
    
    return [{
        "id": h.id,
        "question": h.question,
        "answer": h.answer,
        "timestamp": h.timestamp.isoformat(),
        "user_feedback": h.user_feedback
    } for h in history]
