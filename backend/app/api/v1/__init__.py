"""
API v1 package for Enterprise AI Customer Support Assistant.
"""

from .chat import router as chat_router
from .documents import router as documents_router
from .memory import router as memory_router
from .health import router as health_router
from .auth import router as auth_router

__all__ = ["chat_router", "documents_router", "memory_router", "health_router", "auth_router"]