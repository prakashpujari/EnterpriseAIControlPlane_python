"""
Audit logging module for compliance and observability.
Logs all user actions, model interactions, and system events.
"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.models.database import AuditLog, DriftEvent, PIIDetection
from app.config.settings import settings

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Audit log actions."""

    CHAT_QUERY = "chat_query"
    CHAT_RESPONSE = "chat_response"
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_QUERY = "document_query"
    MEMORY_ACCESS = "memory_access"
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    MODEL_ROUTING = "model_routing"
    DRIFT_DETECTED = "drift_detected"
    PII_DETECTED = "pii_detected"
    RATE_LIMITED = "rate_limited"


class AuditLogger:
    """
    Comprehensive audit logger for compliance and observability.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session

    async def log_action(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        model_used: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        latency_ms: Optional[int] = None,
        outcome: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        Log an audit event.

        Args:
            action: Action being logged
            user_id: User ID (if available)
            role: User role
            resource_type: Type of resource
            resource_id: Resource ID
            request_data: Request payload (sanitized)
            response_data: Response payload (sanitized)
            model_used: LLM model used
            tokens_input: Input tokens
            tokens_output: Output tokens
            latency_ms: Request latency
            outcome: success/failure/blocked
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Audit log ID
        """
        audit_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        audit_entry = {
            "id": audit_id,
            "user_id": user_id,
            "role": role,
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_data": self._sanitize(request_data),
            "response_data": self._sanitize(response_data),
            "model_used": model_used,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "latency_ms": latency_ms,
            "outcome": outcome,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": created_at.isoformat(),
        }

        # Log to structured logs
        logger.info(f"AUDIT: {json.dumps(audit_entry)}")

        # Store in database if session available. The DB column is a DateTime,
        # so pass a real datetime (SQLite rejects an ISO string here).
        if self.db_session:
            try:
                db_entry = {**audit_entry, "created_at": created_at}
                stmt = insert(AuditLog).values(**db_entry)
                await self.db_session.execute(stmt)
                await self.db_session.commit()
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

        return audit_id

    def _sanitize(self, data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Sanitize sensitive data before logging.

        Args:
            data: Data to sanitize

        Returns:
            Sanitized data
        """
        if data is None:
            return None

        sanitized = {}
        sensitive_keys = {"password", "token", "api_key", "secret", "credential"}

        for key, value in data.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize(value)
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[truncated]"
            else:
                sanitized[key] = value

        return sanitized


class DriftDetector:
    """
    Detects drift in model performance and user behavior.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session
        self.metrics: Dict[str, List[float]] = {}

    async def record_metric(
        self,
        name: str,
        value: float,
        threshold: float,
    ) -> Optional[DriftEvent]:
        """
        Record a metric and check for drift.

        Args:
            name: Metric name
            value: Current metric value
            threshold: Drift threshold

        Returns:
            DriftEvent if drift detected, None otherwise
        """
        if name not in self.metrics:
            self.metrics[name] = []

        self.metrics[name].append(value)

        # Keep last 100 values
        if len(self.metrics[name]) > 100:
            self.metrics[name] = self.metrics[name][-100:]

        # Check for drift using simple threshold
        if len(self.metrics[name]) > 10:
            avg = sum(self.metrics[name][-10:]) / 10
            if value > avg * threshold or value < avg / threshold:
                return await self._create_drift_event(name, value, threshold)

        return None

    async def _create_drift_event(
        self,
        name: str,
        value: float,
        threshold: float,
    ) -> DriftEvent:
        """
        Create a drift event.

        Args:
            name: Metric name
            value: Current value
            threshold: Threshold value

        Returns:
            DriftEvent instance
        """
        severity = "medium" if 1.2 <= threshold < 1.5 else "high" if 1.5 <= threshold < 2.0 else "critical"

        event = DriftEvent(
            id=str(uuid.uuid4()),
            metric_name=name,
            metric_value=value,
            threshold=threshold,
            severity=severity,
            mitigation_action=self._suggest_mitigation(name, severity),
            resolved=False,
            created_at=datetime.utcnow(),
        )

        # Log drift event
        logger.warning(f"DRIFT DETECTED: {name}={value}, threshold={threshold}")

        # Store in database
        if self.db_session:
            try:
                stmt = insert(DriftEvent).values(**event.__dict__)
                await self.db_session.execute(stmt)
                await self.db_session.commit()
            except Exception as e:
                logger.error(f"Failed to write drift event: {e}")

        return event

    def _suggest_mitigation(self, metric_name: str, severity: str) -> str:
        """
        Suggest mitigation action based on metric and severity.

        Args:
            metric_name: Name of the drifting metric
            severity: Drift severity

        Returns:
            Suggested mitigation action
        """
        mitigations = {
            "quality_score": "Route traffic to Haiku model, increase grounding threshold",
            "cost_per_request": "Switch to smaller model for compression, enable caching",
            "latency_ms": "Scale up instances, enable response caching",
            "cache_hit_rate": "Review retrieval strategy, adjust chunk size",
            "relevance_score": "Adjust RAG retrieval parameters, re-ranker threshold",
            "user_satisfaction": "Review recent responses, trigger model retraining",
        }

        return mitigations.get(metric_name, "Review and adjust model parameters")


class PIIDetector:
    """
    Detects and logs PII in user content.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db_session = db_session

    async def log_detection(
        self,
        user_id: str,
        session_id: str,
        pii_type: str,
        pii_value_hash: str,
        confidence: float,
        action_taken: str = "redacted",
    ) -> str:
        """
        Log a PII detection event.

        Args:
            user_id: User ID
            session_id: Session ID
            pii_type: Type of PII detected
            pii_value_hash: Hashed PII value (not the actual value)
            confidence: Detection confidence
            action_taken: Action taken (redacted, blocked, etc.)

        Returns:
            Detection log ID
        """
        detection_id = str(uuid.uuid4())

        detection = PIIDetection(
            id=detection_id,
            user_id=user_id,
            session_id=session_id,
            pii_type=pii_type,
            pii_value_hash=pii_value_hash,
            confidence=confidence,
            action_taken=action_taken,
            created_at=datetime.utcnow(),
        )

        logger.info(f"PII DETECTED: type={pii_type}, user={user_id}")

        if self.db_session:
            try:
                stmt = insert(PIIDetection).values(**detection.__dict__)
                await self.db_session.execute(stmt)
                await self.db_session.commit()
            except Exception as e:
                logger.error(f"Failed to write PII detection: {e}")

        return detection_id


# Global instances
audit_logger: Optional[AuditLogger] = None
drift_detector = DriftDetector()
pii_detector = PIIDetector()


def get_audit_logger(db_session: Optional[AsyncSession] = None) -> AuditLogger:
    """Get or create the global audit logger instance."""
    global audit_logger
    if audit_logger is None:
        audit_logger = AuditLogger(db_session)
    return audit_logger


def get_drift_detector(db_session: Optional[AsyncSession] = None) -> DriftDetector:
    """Get or create the global drift detector instance."""
    global drift_detector
    if drift_detector.db_session is None and db_session:
        drift_detector.db_session = db_session
    return drift_detector


def get_pii_detector(db_session: Optional[AsyncSession] = None) -> PIIDetector:
    """Get or create the global PII detector instance."""
    global pii_detector
    if pii_detector.db_session is None and db_session:
        pii_detector.db_session = db_session
    return pii_detector


# Convenience function for logging requests
async def log_request(
    request: Request,
    user_id: Optional[str] = None,
    role: Optional[str] = None,
    action: AuditAction = AuditAction.CHAT_QUERY,
    db_session: Optional[AsyncSession] = None,
) -> str:
    """
    Log an incoming request.

    Args:
        request: FastAPI request
        user_id: User ID
        role: User role
        action: Action being performed
        db_session: Database session

    Returns:
        Audit log ID
    """
    logger_instance = get_audit_logger(db_session)

    # Sanitize request data
    request_data = {}
    if request is not None and hasattr(request, "headers"):
        request_data["headers"] = dict(request.headers)

    return await logger_instance.log_action(
        action=action,
        user_id=user_id,
        role=role,
        request_data=request_data,
        ip_address=request.client.host if request and request.client else None,
        user_agent=request.headers.get("user-agent") if request and hasattr(request, "headers") else None,
    )


async def log_response(
    audit_id: str,
    user_id: Optional[str] = None,
    model_used: Optional[str] = None,
    tokens_input: Optional[int] = None,
    tokens_output: Optional[int] = None,
    latency_ms: Optional[int] = None,
    outcome: str = "success",
    response_data: Optional[Dict[str, Any]] = None,
    db_session: Optional[AsyncSession] = None,
) -> None:
    """
    Log a response (updates an existing audit log).

    Args:
        audit_id: Existing audit log ID
        user_id: User ID
        model_used: LLM model used
        tokens_input: Input tokens
        tokens_output: Output tokens
        latency_ms: Request latency
        outcome: success/failure/blocked
        response_data: Response payload
        db_session: Database session
    """
    logger_instance = get_audit_logger(db_session)

    await logger_instance.log_action(
        action=AuditAction.CHAT_RESPONSE,
        user_id=user_id,
        request_data={"audit_id": audit_id},
        response_data=response_data,
        model_used=model_used,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        latency_ms=latency_ms,
        outcome=outcome,
    )