"""
Memory API router for STM and LTM management.
"""

from typing import Dict, Any, Optional
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db_session
from app.models.database import User
from app.gateway.auth import get_current_active_user
from app.memory.ltm import get_ltm_manager
from app.memory.stm import STMManager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/memory/profile")
async def get_user_profile(
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Get user's memory profile from LTM.

    Args:
        db_session: Database session
        user: Authenticated user

    Returns:
        User profile
    """
    ltm = get_ltm_manager(db_session)
    profile = await ltm.get_user_profile(user.id)
    return profile


@router.get("/memory/search")
async def search_memory(
    query: str,
    top_k: int = 5,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Search user's memory.

    Args:
        query: Search query
        top_k: Number of results
        db_session: Database session
        user: Authenticated user

    Returns:
        Search results
    """
    ltm = get_ltm_manager(db_session)
    results = await ltm.retrieve_facts(user.id, query, top_k)

    return {
        "query": query,
        "results": results,
    }


@router.get("/memory/sessions")
async def list_sessions(
    limit: int = 20,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    List user's conversation sessions.

    Args:
        limit: Maximum sessions to return
        db_session: Database session
        user: Authenticated user

    Returns:
        List of sessions
    """
    result = await db_session.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversation_sessions
        WHERE user_id = :user_id
        ORDER BY updated_at DESC
        LIMIT :limit
        """,
        {"user_id": user.id, "limit": limit},
    )

    sessions = []
    for row in result:
        sessions.append({
            "id": row.id,
            "title": row.title,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })

    return {"sessions": sessions}


@router.delete("/memory/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """
    Delete a conversation session.

    Args:
        session_id: Session ID
        db_session: Database session
        user: Authenticated user

    Returns:
        Success message
    """
    stm = STMManager(db_session)
    await stm.delete_session(session_id)

    return {"message": "Session deleted successfully"}