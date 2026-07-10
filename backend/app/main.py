"""
Main FastAPI application entry point.
Enterprise AI Customer Support Assistant.
"""

import uuid
import logging
from typing import Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import uvicorn

from app.config.settings import settings
from app.config.database import init_db, close_db
from app.config.pinecone_client import init_pinecone_indexes
from app.gateway.auth import get_current_active_user, require_role
from app.gateway.audit import AuditAction, get_audit_logger
from app.orchestration import get_chat_workflow
from app.models.database import User

# LangSmith integration
if settings.LANGSMITH_API_KEY and settings.LANGSMITH_TRACING:
    from langsmith import trace
    import os
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY.get_secret_value()
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise AI Customer Support Assistant with RAG, memory, and agentic orchestration",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware (production)
if settings.ENVIRONMENT == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting Enterprise AI Customer Support Assistant...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize Pinecone indexes
    await init_pinecone_indexes()
    logger.info("Pinecone indexes initialized")

    logger.info(f"Application started in {settings.ENVIRONMENT} mode")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down...")
    await close_db()
    logger.info("Shutdown complete")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    if isinstance(exc, HTTPException):
        # Let FastAPI handle HTTPException normally
        raise exc
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "request_id": str(uuid.uuid4()),
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint."""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


# Include routers
from app.api.v1 import chat, documents, memory, health, auth
from app.api.v1 import settings as settings_router

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(memory.router, prefix="/api/v1", tags=["memory"])
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(settings_router.router, prefix="/api/v1", tags=["settings"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        workers=4 if settings.ENVIRONMENT == "production" else 1,
    )