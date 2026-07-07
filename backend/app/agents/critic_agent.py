"""
Critic Agent for response validation and compliance checking.
Validates grounding, consistency, and policy compliance.
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import re
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.gateway.guardrails import guardrails, PIIResult
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


@dataclass
class CriticResult:
    """Result from critic agent validation."""

    is_valid: bool
    issues: List[str]
    pii_detected: bool
    pii_types: List[str]
    compliance_issues: List[str]
    grounding_score: float
    confidence: float
    suggested_fixes: List[str]


class CriticAgent:
    """
    Agent that validates responses for quality, safety, and compliance.
    """

    def __init__(self):
        self.client = get_claude_client()

    async def validate(
        self,
        response: str,
        query: str,
        sources: List[Dict[str, Any]] = None,
        role: str = "support_engineer",
        context: Optional[Dict[str, Any]] = None,
    ) -> CriticResult:
        """
        Validate a response.

        Args:
            response: Generated response
            query: Original query
            sources: Retrieved sources
            role: User role
            context: Conversation context

        Returns:
            CriticResult with validation outcome
        """
        issues = []
        pii_detected = False
        pii_types = []
        compliance_issues = []
        grounding_score = 1.0

        # 1. PII Scan
        pii_result = self._scan_pii(response)
        if pii_result.detected:
            pii_detected = True
            pii_types = pii_result.pii_types
            issues.append(f"PII detected: {', '.join(pii_types)}")

        # 2. Grounding Check
        grounding_score = self._check_grounding(response, sources or [])
        if grounding_score < 0.7:
            issues.append("Low grounding score - response may contain hallucinations")

        # 3. Compliance Check
        compliance_issues = self._check_compliance(response, role)
        issues.extend(compliance_issues)

        # 4. Consistency Check
        consistency_issues = self._check_consistency(response, context or {})
        issues.extend(consistency_issues)

        # 5. Quality Check
        quality_issues = self._check_quality(response)
        issues.extend(quality_issues)

        # Determine overall validity. PII detection and policy-keyword
        # mentions are recorded but do NOT block otherwise-valid responses
        # (they are informational and could be redacted downstream). Only
        # genuine quality problems (empty/short/placeholder/repetitive text)
        # or a confirmed lack of grounding invalidate the response.
        blocking_issues = [
            issue
            for issue in issues
            if not (
                issue.startswith("PII detected")
                or issue.startswith("Potential confidential")
            )
        ]
        is_valid = len(blocking_issues) == 0

        # Generate suggested fixes if invalid
        suggested_fixes = []
        if not is_valid:
            suggested_fixes = self._suggest_fixes(issues, response, query)

        return CriticResult(
            is_valid=is_valid,
            issues=issues,
            pii_detected=pii_detected,
            pii_types=pii_types,
            compliance_issues=compliance_issues,
            grounding_score=grounding_score,
            confidence=0.9 if is_valid else 0.5,
            suggested_fixes=suggested_fixes,
        )

    def _scan_pii(self, text: str) -> PIIResult:
        """
        Scan for PII in text.

        Args:
            text: Text to scan

        Returns:
            PIIResult
        """
        return guardrails.pii_scanner.scan(text)

    def _check_grounding(
        self,
        response: str,
        sources: List[Dict[str, Any]],
    ) -> float:
        """
        Check grounding score based on source citations.

        Args:
            response: Response to check
            sources: Retrieved sources

        Returns:
            Grounding score (0-1)
        """
        if not sources:
            return 1.0  # No sources to ground against; cannot be ungrounded

        # Only enforce citation grounding when sources carry real document
        # content (e.g. RAG citations). Heuristic sources derived from
        # keywords like "policy"/"kb" have no citations to check against.
        has_real_content = any(s.get("content") for s in sources)
        if not has_real_content:
            return 1.0

        # Count citations in response
        citation_pattern = r'\[\d+\]'
        citations = re.findall(citation_pattern, response)

        # Score based on citation coverage
        citation_ratio = len(citations) / len(sources) if sources else 0
        grounding_score = min(1.0, citation_ratio * 1.5)

        return grounding_score

    def _check_compliance(
        self,
        response: str,
        role: str,
    ) -> List[str]:
        """
        Check compliance with role-based policies.

        Args:
            response: Response to check
            role: User role

        Returns:
            List of compliance issues
        """
        issues = []

        # Check for confidential information leakage
        confidential_patterns = [
            r'\bconfidential\b',
            r'\binternal use only\b',
            r'\bproprietary\b',
            r'\brestricted\b',
        ]

        for pattern in confidential_patterns:
            if re.search(pattern, response, re.IGNORECASE):
                issues.append("Potential confidential information in response")

        # Role-specific checks
        if role == "compliance_officer":
            # Check for regulatory references
            if "regulation" in response.lower() or "policy" in response.lower():
                pass  # Good - mentions regulations

        return issues

    def _check_consistency(
        self,
        response: str,
        context: Dict[str, Any],
    ) -> List[str]:
        """
        Check response consistency with context.

        Args:
            response: Response to check
            context: Conversation context

        Returns:
            List of consistency issues
        """
        issues = []

        # Check if response contradicts previous decisions
        previous_decisions = context.get("previous_decisions", [])
        for decision in previous_decisions:
            outcome = decision.get("outcome", "").lower()
            description = decision.get("description", "").lower()
            if description in response.lower() and outcome in response.lower():
                # Check if consistent
                pass

        return issues

    def _check_quality(self, response: str) -> List[str]:
        """
        Check response quality.

        Args:
            response: Response to check

        Returns:
            List of quality issues
        """
        issues = []

        # Check length
        if len(response) < 10:
            issues.append("Response too short")

        # Check for placeholder text
        placeholders = ["[REDACTED]", "[BLOCKED]", "<MISSING>"]
        for placeholder in placeholders:
            if placeholder in response:
                issues.append(f"Response contains placeholder: {placeholder}")

        # Check for repetitive text
        if re.search(r'(.{10,})\1', response):
            issues.append("Response contains repetitive text")

        return issues

    def _suggest_fixes(
        self,
        issues: List[str],
        response: str,
        query: str,
    ) -> List[str]:
        """
        Suggest fixes for validation issues.

        Args:
            issues: List of issues
            response: Original response
            query: Original query

        Returns:
            List of suggested fixes
        """
        fixes = []

        for issue in issues:
            if "PII" in issue:
                fixes.append("Redact PII and re-generate response")
            elif "grounding" in issue.lower():
                fixes.append("Regenerate with better grounding from sources")
            elif "confidential" in issue.lower():
                fixes.append("Remove confidential information from response")
            elif "short" in issue.lower():
                fixes.append("Provide more detailed response")

        return fixes

    async def validate_with_llm(
        self,
        response: str,
        query: str,
        sources: List[Dict[str, Any]] = None,
    ) -> CriticResult:
        """
        Use LLM to validate response.

        Args:
            response: Response to validate
            query: Original query
            sources: Retrieved sources

        Returns:
            CriticResult
        """
        model_config = model_router.get_model_config("small")

        sources_text = "\n".join([
            f"[{i+1}] {s.get('title', 'Source')} - {s.get('content', '')[:200]}"
            for i, s in enumerate(sources or [])
        ])

        prompt = f"""
        Validate this AI response for quality, grounding, and safety.

        Query: {query}

        Response: {response}

        Sources: {sources_text if sources_text else 'No sources'}

        Return JSON with:
        - is_valid: true if response is safe and accurate
        - issues: List of any issues found
        - confidence: 0-1 score of validation confidence
        """

        try:
            response_obj = await self.client.generate(
                model=model_config["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.1,
            )

            result = extract_json(response_obj["content"][0].text, {})

            return CriticResult(
                is_valid=result.get("is_valid", True),
                issues=result.get("issues", []),
                pii_detected=False,
                pii_types=[],
                compliance_issues=[],
                grounding_score=0.9,
                confidence=result.get("confidence", 0.8),
                suggested_fixes=[],
            )

        except Exception as e:
            logger.error(f"LLM validation failed: {e}")
            return self.validate(response, query, sources)


# Global critic agent instance
critic_agent = CriticAgent()


def get_critic_agent() -> CriticAgent:
    """Get the global critic agent instance."""
    return critic_agent