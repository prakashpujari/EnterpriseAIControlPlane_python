"""
Guardrails module for prompt governance, PII scanning, and content filtering.
"""

import re
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

from app.config.settings import settings
from app.models.database import PIIDetection, PIIDetectionType

logger = logging.getLogger(__name__)


@dataclass
class PIIPattern:
    """Pattern for detecting PII."""

    name: str
    pattern: re.Pattern
    confidence: float = 0.9
    replacement: str = "[REDACTED]"


@dataclass
class PIIResult:
    """Result of PII scanning."""

    detected: bool = False
    pii_types: List[str] = field(default_factory=list)
    pii_values: List[Dict[str, Any]] = field(default_factory=list)
    redacted_text: str = ""


class PIIScanner:
    """
    Scans text for PII (Personally Identifiable Information).
    """

    # Common PII patterns
    PATTERNS = [
        PIIPattern(
            name="email",
            pattern=re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            confidence=0.95,
        ),
        PIIPattern(
            name="phone",
            pattern=re.compile(
                r'\b(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ),
            confidence=0.85,
        ),
        PIIPattern(
            name="ssn",
            pattern=re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            confidence=0.99,
        ),
        PIIPattern(
            name="credit_card",
            pattern=re.compile(
                r'\b(?:\d[ -]*?){13,16}\b'
            ),
            confidence=0.8,
        ),
        PIIPattern(
            name="ip_address",
            pattern=re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
            confidence=0.9,
        ),
        PIIPattern(
            name="date",
            pattern=re.compile(
                r'\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b|\b\d{1,2}/\d{1,2}/\d{2}\b'
            ),
            confidence=0.7,
        ),
    ]

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and settings.PII_ENABLED

    def scan(self, text: str, threshold: float = None) -> PIIResult:
        """
        Scan text for PII.

        Args:
            text: Text to scan
            threshold: Confidence threshold (default from settings)

        Returns:
            PIIResult with detected PII information
        """
        if not self.enabled:
            return PIIResult(detected=False, redacted_text=text)

        if threshold is None:
            threshold = settings.PII_CONFIDENCE_THRESHOLD

        result = PIIResult(detected=False, redacted_text=text)
        redacted_text = text

        for pattern in self.PATTERNS:
            matches = pattern.pattern.findall(text)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1] if len(match) > 1 else match

                    result.detected = True
                    result.pii_types.append(pattern.name)

                    # Hash the PII value for privacy
                    pii_hash = hashlib.sha256(match.encode()).hexdigest()[:16]

                    result.pii_values.append({
                        "type": pattern.name,
                        "confidence": pattern.confidence,
                        "hash": pii_hash,
                    })

                    # Redact the PII
                    redacted_text = redacted_text.replace(match, pattern.replacement)

        result.redacted_text = redacted_text
        result.pii_types = list(set(result.pii_types))  # Remove duplicates

        return result

    def is_pii_safe(self, text: str) -> bool:
        """
        Check if text contains no PII above threshold.

        Args:
            text: Text to check

        Returns:
            True if no PII detected, False otherwise
        """
        result = self.scan(text)
        return not result.detected


class PromptGuardrail:
    """
    Validates and sanitizes prompts before sending to LLM.
    """

    # Dangerous patterns that might indicate prompt injection
    DANGEROUS_PATTERNS = [
        re.compile(r'ignore\s+(all\s+)?(previous\s+)?instructions?', re.IGNORECASE),
        re.compile(r'disregard\s+(all\s+)?(previous\s+)?instructions?', re.IGNORECASE),
        re.compile(r'forget\s+(all\s+)?(previous\s+)?context', re.IGNORECASE),
        re.compile(r'role\s+=\s*["\']?system', re.IGNORECASE),
        re.compile(r'user\s+=\s*["\']?ignore', re.IGNORECASE),
    ]

    def __init__(self, max_length: int = 10000):
        self.max_length = max_length

    def validate(self, prompt: str) -> Tuple[bool, List[str]]:
        """
        Validate a prompt for safety.

        Args:
            prompt: Prompt to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check length
        if len(prompt) > self.max_length:
            issues.append(f"Prompt exceeds maximum length of {self.max_length}")

        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(prompt):
                issues.append("Potential prompt injection detected")

        # Check for excessive whitespace/special characters
        if re.search(r'[^\S\n]{10,}', prompt):
            issues.append("Excessive whitespace detected")

        return len(issues) == 0, issues

    def sanitize(self, prompt: str) -> str:
        """
        Sanitize a prompt by removing dangerous content.

        Args:
            prompt: Prompt to sanitize

        Returns:
            Sanitized prompt
        """
        sanitized = prompt

        for pattern in self.DANGEROUS_PATTERNS:
            sanitized = pattern.sub("[BLOCKED]", sanitized)

        return sanitized


class ContentFilter:
    """
    Filters content based on role-based policies.
    """

    # Content policies by role
    ROLE_POLICIES = {
        "support_engineer": {
            "allowed_topics": ["customer", "ticket", "issue", "refund", "account", "billing"],
            "blocked_keywords": ["confidential", "internal only"],
        },
        "mortgage_analyst": {
            "allowed_topics": ["mortgage", "loan", "application", "approval", "interest rate"],
            "blocked_keywords": ["proprietary", "internal"],
        },
        "compliance_officer": {
            "allowed_topics": ["regulation", "compliance", "audit", "policy", "legal"],
            "blocked_keywords": ["confidential", "internal"],
        },
        "product_owner": {
            "allowed_topics": ["feature", "product", "release", "roadmap", "user story"],
            "blocked_keywords": ["confidential", "internal"],
        },
    }

    def filter_response(
        self,
        response: str,
        role: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str]]:
        """
        Filter response based on role policy.

        Args:
            response: Response to filter
            role: User role
            context: Optional context for filtering

        Returns:
            Tuple of (filtered_response, list of blocked items)
        """
        blocked_items = []

        if role not in self.ROLE_POLICIES:
            return response, blocked_items

        policy = self.ROLE_POLICIES[role]

        # Check for blocked keywords
        for keyword in policy.get("blocked_keywords", []):
            if keyword.lower() in response.lower():
                blocked_items.append(keyword)

        return response, blocked_items


class GuardrailsManager:
    """
    Main guardrails manager that coordinates all checks.
    """

    def __init__(self):
        self.pii_scanner = PIIScanner(enabled=settings.PII_ENABLED)
        self.prompt_guard = PromptGuardrail()
        self.content_filter = ContentFilter()

    def scan_and_redact(
        self,
        text: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> PIIResult:
        """
        Scan text for PII and redact sensitive information.

        Args:
            text: Text to scan
            user_id: Optional user ID for logging
            session_id: Optional session ID for logging

        Returns:
            PIIResult with redacted text
        """
        result = self.pii_scanner.scan(text)

        if result.detected and user_id:
            # Log PII detections
            for pii_value in result.pii_values:
                logger.info(
                    f"PII detected: type={pii_value['type']}, "
                    f"user_id={user_id}, session_id={session_id}"
                )

        return result

    def validate_prompt(self, prompt: str) -> Tuple[bool, List[str], str]:
        """
        Validate and sanitize a prompt.

        Args:
            prompt: Prompt to validate

        Returns:
            Tuple of (is_valid, issues, sanitized_prompt)
        """
        is_valid, issues = self.prompt_guard.validate(prompt)
        sanitized = self.prompt_guard.sanitize(prompt)
        return is_valid, issues, sanitized

    def filter_response(
        self,
        response: str,
        role: str,
    ) -> Tuple[str, List[str]]:
        """
        Filter response based on role policy.

        Args:
            response: Response to filter
            role: User role

        Returns:
            Tuple of (filtered_response, blocked_items)
        """
        return self.content_filter.filter_response(response, role)


# Global guardrails manager instance
guardrails = GuardrailsManager()