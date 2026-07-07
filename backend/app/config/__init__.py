"""
Configuration package for Enterprise AI Customer Support Assistant.
"""

from .settings import settings, RoleType, ModelTier, QueryType
from .database import engine, get_db_session, init_db, close_db, Base
from .pinecone_client import pc, get_rag_index, get_ltm_index, get_namespace
from .llm_providers import get_claude_client, model_router, ClaudeClient

__all__ = [
    "settings",
    "RoleType",
    "ModelTier",
    "QueryType",
    "engine",
    "get_db_session",
    "init_db",
    "close_db",
    "Base",
    "pc",
    "get_rag_index",
    "get_ltm_index",
    "get_namespace",
    "get_claude_client",
    "model_router",
    "ClaudeClient",
]