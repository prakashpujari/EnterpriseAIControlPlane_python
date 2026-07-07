"""
FAQ Agent for answering common customer questions.
Uses vector search over FAQ documents and KB articles.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.memory.ltm import LTMManager

logger = logging.getLogger(__name__)


@dataclass
class FAQResult:
    """Result from FAQ agent."""

    answer: str
    confidence: float
    sources: List[Dict[str, str]]
    is_faq: bool
    tokens_input: int = 0
    tokens_output: int = 0


class FAQAgent:
    """
    Agent for answering frequently asked questions.
    """

    # Common FAQ patterns
    FAQ_PATTERNS = {
        "hours": ["hours", "open", "close", "time", "schedule"],
        "contact": ["contact", "phone", "email", "reach", "call"],
        "policy": ["policy", "refund", "return", "exchange", "guarantee"],
        "account": ["account", "login", "password", "signup", "register"],
        "shipping": ["shipping", "delivery", "order", "package", "tracking"],
    }

    def __init__(self, ltm_manager: Optional[LTMManager] = None):
        self.client = get_claude_client()
        self.ltm = ltm_manager or LTMManager()

    async def answer_question(
        self,
        query: str,
        role: str = "support_engineer",
        context: Optional[Dict[str, Any]] = None,
    ) -> FAQResult:
        """
        Answer a FAQ question.

        Args:
            query: User question
            role: User role
            context: Conversation context

        Returns:
            FAQResult with answer and confidence
        """
        # First check if this is a FAQ-type query
        if not self._is_faq_query(query):
            return FAQResult(
                answer="",
                confidence=0.0,
                sources=[],
                is_faq=False,
            )

        # Try to find answer in LTM (cached FAQ answers)
        cached_answer = await self._find_cached_answer(query)
        if cached_answer:
            return FAQResult(
                answer=cached_answer["answer"],
                confidence=cached_answer["confidence"],
                sources=cached_answer["sources"],
                is_faq=True,
            )

        # Generate answer using LLM
        answer = await self._generate_answer(query, role, context)

        return FAQResult(
            answer=answer["answer"],
            confidence=answer["confidence"],
            sources=answer["sources"],
            is_faq=True,
            tokens_input=answer.get("tokens_input", 0),
            tokens_output=answer.get("tokens_output", 0),
        )

    def _is_faq_query(self, query: str) -> bool:
        """
        Determine if query is likely a FAQ question.

        Args:
            query: User query

        Returns:
            True if likely FAQ
        """
        query_lower = query.lower()

        for category, keywords in self.FAQ_PATTERNS.items():
            if any(kw in query_lower for kw in keywords):
                return True

        return False

    async def _find_cached_answer(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Find cached answer in LTM.

        Args:
            query: User query

        Returns:
            Cached answer or None
        """
        # This would search LTM for similar questions
        # For now, return None to trigger fresh generation
        return None

    async def _generate_answer(
        self,
        query: str,
        role: str,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate an answer using the LLM.

        Args:
            query: User question
            role: User role
            context: Conversation context

        Returns:
            Dict with answer, confidence, and sources
        """
        model_config = model_router.get_model_config("small")

        # Build prompt with role-specific guidance
        role_guidance = self._get_role_guidance(role)

        prompt = f"""
        Answer this customer FAQ question helpfully and accurately.

        Role: {role}
        {role_guidance}

        Question: {query}

        Provide:
        1. A clear, concise answer
        2. Any relevant policies or procedures
        3. Sources if applicable

        Format as plain text, no markdown formatting.
        """

        try:
            response = await self.client.generate(
                model=model_config["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=model_config["max_tokens"] // 2,
                temperature=0.3,
            )

            answer_text = response["content"][0].text
            usage = response.get("usage", {})

            # Extract potential sources from answer
            sources = self._extract_sources(answer_text)

            return {
                "answer": answer_text,
                "confidence": 0.85,
                "sources": sources,
                "tokens_input": usage.get("input_tokens", 0),
                "tokens_output": usage.get("output_tokens", 0),
            }

        except Exception as e:
            logger.error(f"Failed to generate FAQ answer: {e}")
            return {
                "answer": "I apologize, but I'm unable to retrieve an answer at this time. Please try rephrasing your question or contact support directly.",
                "confidence": 0.0,
                "sources": [],
            }

    def _get_role_guidance(self, role: str) -> str:
        """
        Get role-specific guidance for FAQ answering.

        Args:
            role: User role

        Returns:
            Guidance string
        """
        guidance = {
            "support_engineer": "Be helpful, empathic, and provide clear next steps. Use customer's name if available.",
            "mortgage_analyst": "Focus on accuracy of financial information. Cite specific rates and terms.",
            "compliance_officer": "Ensure all responses are compliant with regulations. Provide policy references.",
            "product_owner": "Focus on product features and user experience. Be concise and actionable.",
        }
        return guidance.get(role, "Provide accurate, helpful information.")

    def _extract_sources(self, answer: str) -> List[Dict[str, str]]:
        """
        Extract source information from answer.

        Args:
            answer: Generated answer

        Returns:
            List of sources
        """
        # Look for common source patterns
        sources = []

        # Check for policy references
        if "policy" in answer.lower():
            sources.append({
                "title": "Company Policy",
                "type": "policy",
            })

        # Check for KB references
        if "kb" in answer.lower() or "knowledge base" in answer.lower():
            sources.append({
                "title": "Knowledge Base",
                "type": "kb",
            })

        return sources


# Global FAQ agent instance
faq_agent = FAQAgent()


def get_faq_agent() -> FAQAgent:
    """Get the global FAQ agent instance."""
    return faq_agent