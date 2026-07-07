"""
Chat API router for Enterprise AI Customer Support Assistant.
Handles chat requests with full agentic workflow.
"""

from typing import Dict, Any, Optional
import time
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db_session
from app.config.settings import settings
from app.models.database import ChatRequest, ChatResponse, User
from app.gateway.auth import get_current_active_user
from app.gateway.rate_limiter import rate_limiter, check_rate_limit
from app.gateway.audit import log_request, log_response, AuditAction
from app.orchestration import get_chat_workflow
from app.memory.stm import STMManager
from app.memory.ltm import get_ltm_manager
from app.memory.agents import get_memory_agent

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> ChatResponse:
    """
    Process a chat query through the agentic workflow.

    Args:
        request: Chat request with query and role
        db_session: Database session
        user: Authenticated user

    Returns:
        ChatResponse with answer and metadata
    """
    start_time = time.time()

    # Log the request
    await log_request(
        request=request._request if hasattr(request, '_request') else None,
        user_id=user.id,
        role=user.role,
        action=AuditAction.CHAT_QUERY,
        db_session=db_session,
    )

    # Get workflow
    workflow = get_chat_workflow(db_session)

    # Process query with user_id from authenticated user
    response = await workflow.process_query(request, user_id=user.id)

    # Log the response
    await log_response(
        audit_id="",
        user_id=user.id,
        model_used=response.model_used,
        tokens_input=response.tokens_input,
        tokens_output=response.tokens_output,
        latency_ms=response.latency_ms,
        outcome="success" if response.is_valid else "blocked",
        response_data={"response": response.response[:100]},
        db_session=db_session,
    )

    return response


@router.post("/chat/session", response_model=dict)
async def create_session(
    role: str,
    title: Optional[str] = None,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Create a new conversation session.

    Args:
        role: User role for session
        title: Optional session title
        db_session: Database session
        user: Authenticated user

    Returns:
        Session info
    """
    stm = STMManager(db_session)
    session_id = await stm.create_session(
        user_id=user.id,
        role=role,
        title=title,
    )

    return {
        "session_id": session_id,
        "role": role,
        "created_at": time.time(),
    }


@router.get("/chat/session/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get conversation session with turns.

    Args:
        session_id: Session ID
        db_session: Database session
        user: Authenticated user

    Returns:
        Session with turns
    """
    stm = STMManager(db_session)
    session = await stm.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session.id,
        "role": session.role,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "turns": [
            {
                "id": t.id,
                "turn_number": t.turn_number,
                "role": t.role,
                "content": t.content,
                "model_used": t.model_used,
                "tokens_used": t.tokens_used,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in session.turns
        ],
    }


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    Stream chat response (SSE).

    Args:
        request: Chat request
        db_session: Database session
        user: Authenticated user

    Returns:
        Server-sent events stream
    """
    from fastapi.responses import StreamingResponse

    workflow = get_chat_workflow(db_session)

    async def generate():
        # Process and stream response
        response = await workflow.process_query(request)

        # Send initial data
        yield f"data: {response.response}\n\n"

        # Send metadata
        yield f"data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/plain")


@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
    limit: int = 10,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    Get chat history for a session.

    Args:
        session_id: Session ID
        limit: Number of turns to return
        db_session: Database session
        user: Authenticated user

    Returns:
        Chat history
    """
    stm = STMManager(db_session)
    turns = await stm.get_recent_turns(session_id, limit)

    return {
        "session_id": session_id,
        "turns": [
            {
                "role": t.role,
                "content": t.content,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in turns
        ],
    }