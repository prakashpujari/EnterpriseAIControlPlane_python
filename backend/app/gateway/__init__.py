"""
Gateway package for Enterprise AI Customer Support Assistant.
Provides authentication, RBAC, model routing, and guardrails.
"""

from .auth import (
    get_current_user,
    get_current_active_user,
    create_access_token,
    decode_token,
    require_role,
    require_permission,
    oauth2_scheme,
)
from .guardrails import (
    guardrails,
    PIIScanner,
    PromptGuardrail,
    ContentFilter,
    PIIResult,
)
from .rate_limiter import (
    RateLimiter,
    rate_limiter,
    TokenBucket,
    check_rate_limit,
)
from .audit import (
    AuditLogger,
    DriftDetector,
    PIIDetector,
    get_audit_logger,
    get_drift_detector,
    get_pii_detector,
    AuditAction,
    log_request,
    log_response,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "create_access_token",
    "decode_token",
    "require_role",
    "require_permission",
    "oauth2_scheme",
    "guardrails",
    "PIIScanner",
    "PromptGuardrail",
    "ContentFilter",
    "PIIResult",
    "RateLimiter",
    "rate_limiter",
    "TokenBucket",
    "check_rate_limit",
    "AuditLogger",
    "DriftDetector",
    "PIIDetector",
    "get_audit_logger",
    "get_drift_detector",
    "get_pii_detector",
    "AuditAction",
    "log_request",
    "log_response",
]