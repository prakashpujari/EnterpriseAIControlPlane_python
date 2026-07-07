"""
Database configuration and connection management.
Uses SQLAlchemy 2.0 with async support.
"""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from .settings import settings


# Convert sync PostgreSQL URL to async
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("sqlite://"):
    # For SQLite, use aiosqlite
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
elif not DATABASE_URL.startswith("postgresql+asyncpg://"):
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    else:
        DATABASE_URL = f"postgresql+asyncpg://{DATABASE_URL}"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,  # 1 hour
)

# Create session maker
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base class for models
Base = declarative_base()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.
    Use as FastAPI dependency.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        from app.models.database import (
            User,
            ConversationSession,
            ConversationTurn,
            ConversationSummary,
            Role,
            UserRole,
            Permission,
            AuditLog,
            DriftEvent,
            PIIDetection,
            Document,
            DocumentChunk,
        )
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()