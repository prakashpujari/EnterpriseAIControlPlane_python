"""
SQLAlchemy database models for Enterprise AI Customer Support Assistant.
Defines all database tables and relationships.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Float,
    Text,
    Enum,
    Table,
    func,
    Index,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from app.config.database import Base


class JSONBType(TypeDecorator):
    """JSONB type that works with both PostgreSQL and SQLite."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class UserRole(PyEnum):
    SUPPORT_ENGINEER = "support_engineer"
    MORTGAGE_ANALYST = "mortgage_analyst"
    COMPLIANCE_OFFICER = "compliance_officer"
    PRODUCT_OWNER = "product_owner"


class QueryType(PyEnum):
    FAQ = "faq"
    RAG = "rag"
    SUMMARIZE = "summarize"
    REASON = "reason"


class ValidationOutcome(PyEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"


class Severity(PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PIIDetectionType(PyEnum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"
    CUSTOM = "custom"


# Association table for user roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id"), primary_key=True),
    Column("role_id", String(50), ForeignKey("roles.id"), primary_key=True),
    Column("granted_by", String(36), ForeignKey("users.id"), nullable=True),
    Column("granted_at", DateTime(timezone=True), server_default=func.now()),
)


class User(Base):
    """User model with RBAC support."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255))
    role = Column(String(50), nullable=False)
    department = Column(String(100))
    password_hash = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions = relationship("ConversationSession", back_populates="user")
    granted_roles = relationship(
        "Role",
        secondary=user_roles,
        backref="users",
        primaryjoin="User.id==user_roles.c.user_id",
        secondaryjoin="Role.id==user_roles.c.role_id",
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class ConversationSession(Base):
    """Conversation session model."""

    __tablename__ = "conversation_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    role = Column(String(50), nullable=False)
    title = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")
    turns = relationship("ConversationTurn", back_populates="session", order_by="ConversationTurn.turn_number")
    summaries = relationship("ConversationSummary", back_populates="session")

    def __repr__(self):
        return f"<ConversationSession(id={self.id}, role={self.role})>"


class ConversationTurn(Base):
    """Individual conversation turns (short-term memory)."""

    __tablename__ = "conversation_turns"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer)
    model_used = Column(String(100))
    doc_metadata = Column(JSONBType)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_session_turn", "session_id", "turn_number"),
        Index("idx_created_at", "created_at"),
    )

    # Relationships
    session = relationship("ConversationSession", back_populates="turns")

    def __repr__(self):
        return f"<ConversationTurn(id={self.id}, session_id={self.session_id}, turn={self.turn_number})>"


class ConversationSummary(Base):
    """Compressed conversation summary (STM compression)."""

    __tablename__ = "conversation_summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=False)
    turn_range_start = Column(Integer, nullable=False)
    turn_range_end = Column(Integer, nullable=False)
    user_goals = Column(JSONBType)  # List of strings
    decisions_made = Column(JSONBType)  # List of dicts
    key_facts = Column(JSONBType)  # Dict of fact -> value
    constraints = Column(JSONBType)  # Dict of constraint -> value
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("ConversationSession", back_populates="summaries")

    def __repr__(self):
        return f"<ConversationSummary(id={self.id}, session_id={self.session_id})>"


class Role(Base):
    """Role definition model with permissions."""

    __tablename__ = "roles"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    token_limit = Column(Integer, default=8000)
    max_tokens_per_request = Column(Integer, default=4000)
    allowed_models = Column(JSONBType)  # List of model names
    allowed_tools = Column(JSONBType)  # List of tool names
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


class Permission(Base):
    """Permission model for fine-grained access control."""

    __tablename__ = "permissions"

    id = Column(String(100), primary_key=True)
    role_id = Column(String(50), ForeignKey("roles.id"), nullable=False)
    resource = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Permission(id={self.id}, role={self.role_id})>"


class AuditLog(Base):
    """Audit log for compliance and security."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    role = Column(String(50))
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(255))
    request_data = Column(JSONBType)
    response_data = Column(JSONBType)
    model_used = Column(String(100))
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    latency_ms = Column(Integer)
    outcome = Column(String(20), nullable=False)
    ip_address = Column(String(45))  # IPv4/IPv6
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes for efficient querying
    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_created", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, outcome={self.outcome})>"


class DriftEvent(Base):
    """Drift detection event for AIOps/LLMOps."""

    __tablename__ = "drift_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float)
    threshold = Column(Float)
    severity = Column(String(20), nullable=False)
    mitigation_action = Column(String(255))
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_drift_metric", "metric_name"),
        Index("idx_drift_severity", "severity"),
        Index("idx_drift_resolved", "resolved"),
    )

    def __repr__(self):
        return f"<DriftEvent(id={self.id}, metric={self.metric_name}, severity={self.severity})>"


class PIIDetection(Base):
    """PII detection log for compliance."""

    __tablename__ = "pii_detections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    session_id = Column(String(36), ForeignKey("conversation_sessions.id"), nullable=True)
    pii_type = Column(String(50), nullable=False)
    pii_value_hash = Column(String(255))  # Hash for privacy
    confidence = Column(Float)
    action_taken = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_pii_type", "pii_type"),
        Index("idx_pii_user", "user_id"),
    )

    def __repr__(self):
        return f"<PIIDetection(id={self.id}, type={self.pii_type})>"


class Document(Base):
    """Document model for RAG."""

    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    content = Column(Text)
    content_type = Column(String(50))  # pdf, docx, txt, html, url
    source_url = Column(Text)
    s3_key = Column(String(500))
    namespace = Column(String(100))
    role_restriction = Column(JSONBType)  # List of roles
    doc_metadata = Column(JSONBType)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_documents_title", "title"),
        Index("idx_documents_namespace", "namespace"),
        Index("idx_documents_active", "is_active"),
    )

    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title})>"


class DocumentChunk(Base):
    """Document chunk model for RAG retrieval."""

    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(JSONBType)  # Embedding vector stored as JSON array
    token_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_chunks_document", "document_id"),
        Index("idx_chunks_chunk_index", "document_id", "chunk_index"),
    )

    # Relationships
    document = relationship("Document", back_populates="chunks")

    def __repr__(self):
        return f"<DocumentChunk(id={self.id}, doc_id={self.document_id}, chunk={self.chunk_index})>"


# Response schemas for API
from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict


class QueryTypeModel(str, PyEnum):
    FAQ = "faq"
    RAG = "rag"
    SUMMARIZE = "summarize"
    REASON = "reason"


class ValidationResult(BaseModel):
    """Result of Critic agent validation."""

    is_valid: bool
    issues: List[str] = []
    pii_detected: bool = False
    pii_types: List[str] = []
    compliance_issues: List[str] = []

    model_config = {"extra": "forbid"}


class DriftMetric(BaseModel):
    """Drift detection metric."""

    name: str
    current_value: float
    threshold: float
    is_drift_detected: bool
    severity: str
    suggested_action: Optional[str] = None

    model_config = {"extra": "forbid"}


class ChatRequest(BaseModel):
    """Chat request model."""

    query: str
    session_id: Optional[str] = None
    role: str
    context: Optional[Dict[str, Any]] = None

    model_config = {"extra": "forbid"}


class ChatResponse(BaseModel):
    """Chat response model."""

    response: str
    session_id: str
    sources: List[Dict[str, Any]] = []
    model_used: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    is_valid: bool = True
    suggestions: List[str] = []

    model_config = {"extra": "forbid"}