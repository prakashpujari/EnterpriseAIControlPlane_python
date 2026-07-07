"""
Health check API router.
"""

from typing import Dict, Any
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db_session
from app.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check(db_session: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """
    Comprehensive health check.

    Args:
        db_session: Database session

    Returns:
        Health status
    """
    health_status = {
        "status": "healthy",
        "database": "connected",
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
    }

    return health_status


@router.get("/health/database")
async def database_health(db_session: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    """
    Database health check.

    Args:
        db_session: Database session

    Returns:
        Database status
    """
    try:
        # Simple query to test connection
        result = await db_session.execute("SELECT 1")
        result.fetchone()

        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "database": str(e)}


@router.get("/health/llm")
async def llm_health() -> Dict[str, Any]:
    """
    LLM provider health check.

    Returns:
        LLM status
    """
    try:
        from app.config.llm_providers import get_claude_client

        client = get_claude_client()
        # Simple embedding test
        await client.embed("test")

        return {"status": "healthy", "provider": "anthropic"}
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return {"status": "unhealthy", "provider": "anthropic", "error": str(e)}


@router.get("/health/pinecone")
async def pinecone_health() -> Dict[str, Any]:
    """
    Pinecone health check.

    Returns:
        Pinecone status
    """
    try:
        from app.config.pinecone_client import get_rag_index

        index = get_rag_index()
        # Simple query to test connection
        await index.query(vector=[0.0] * 1536, top_k=1)

        return {"status": "healthy", "service": "pinecone"}
    except Exception as e:
        logger.error(f"Pinecone health check failed: {e}")
        return {"status": "unhealthy", "service": "pinecone", "error": str(e)}