"""
Central configuration settings for Enterprise AI Customer Support Assistant.
Uses Pydantic for environment variable management and validation.
"""

import os
from pathlib import Path
from typing import List, Optional, Literal
from pydantic import Field, field_validator, SecretStr
from pydantic_settings import BaseSettings
from enum import Enum

# Load .env from backend directory explicitly
backend_dir = Path(__file__).parent.parent.parent
env_path = backend_dir / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path, override=True)


class RoleType(str, Enum):
    SUPPORT_ENGINEER = "support_engineer"
    MORTGAGE_ANALYST = "mortgage_analyst"
    COMPLIANCE_OFFICER = "compliance_officer"
    PRODUCT_OWNER = "product_owner"


class ModelTier(str, Enum):
    SMALL = "small"      # Llama-3.1-8b-instant
    MEDIUM = "medium"    # Llama-3.1-70b-versatile
    LARGE = "large"    # Mixtral-8x7b-32768


class QueryType(str, Enum):
    FAQ = "faq"
    RAG = "rag"
    SUMMARIZE = "summarize"
    REASON = "reason"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Enterprise AI Customer Support Assistant"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database
    DATABASE_URL: str = Field(..., env="DATABASE_URL")
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_RATE_LIMIT_TTL: int = 3600  # 1 hour

    # Pinecone
    PINECONE_API_KEY: SecretStr = Field(..., env="PINECONE_API_KEY")
    PINECONE_ENVIRONMENT: str = Field(default="us-west-2")
    PINECONE_RAG_INDEX: str = Field(default="mortgageindex")
    PINECONE_LTM_INDEX: str = Field(default="mortgageindex")
    PINECONE_HOST: Optional[str] = None
    MORTGAGE_API_KEY: Optional[SecretStr] = None

    # Groq API
    GROQ_API_KEY: SecretStr = Field(..., env="GROQ_API_KEY")
    GROQ_BASE_URL: str = "https://api.groq.com"

    # Model Configuration (Groq models)
    SMALL_MODEL: str = "llama-3.1-8b-instant"      # Fast, cheap for FAQ/compression
    MEDIUM_MODEL: str = "llama-3.1-70b-versatile"      # Good balance for RAG/summarize
    LARGE_MODEL: str = "mixtral-8x7b-32768"  # Complex reasoning

    # Token Limits per Role
    SUPPORT_ENGINEER_TOKEN_LIMIT: int = 8000
    MORTGAGE_ANALYST_TOKEN_LIMIT: int = 10000
    COMPLIANCE_OFFICER_TOKEN_LIMIT: int = 12000
    PRODUCT_OWNER_TOKEN_LIMIT: int = 8000

    # Rate Limits
    REQUESTS_PER_MINUTE_PER_USER: int = 60
    REQUESTS_PER_HOUR_PER_USER: int = 500

    # RAG Configuration
    RAG_TOP_K: int = 20
    RAG_FINAL_K: int = 5
    RAG_RE_RANKER_THRESHOLD: float = 0.7

    # Memory Configuration
    STM_MAX_TURNS: int = 5
    STM_SUMMARY_THRESHOLD: int = 10

    # Drift Detection Thresholds
    QUALITY_THRESHOLD: float = 0.7
    COST_SPIKE_THRESHOLD: float = 1.5  # 50% increase
    LATENCY_THRESHOLD_MS: int = 5000

    # PII Scanning
    PII_ENABLED: bool = True
    PII_CONFIDENCE_THRESHOLD: float = 0.8

    # LangSmith
    LANGSMITH_API_KEY: Optional[SecretStr] = None
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGSMITH_TRACING: bool = True
    LANGSMITH_PROJECT: str = "enterprise-ai-customer-support"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Security
    JWT_SECRET_KEY: SecretStr = Field(..., env="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60

    # Development-only auth bypass. When True, protected endpoints return a
    # built-in dev user instead of requiring a JWT. NEVER enable in production.
    DISABLE_AUTH: bool = False

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "https://localhost:3000"]

    @field_validator("DATABASE_URL", "GROQ_API_KEY", "PINECONE_API_KEY", "JWT_SECRET_KEY", mode="before")
    @classmethod
    def validate_required(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} is required")
        return v

    class Config:
        env_file = None  # Disable auto .env loading, we load manually via python-dotenv
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()