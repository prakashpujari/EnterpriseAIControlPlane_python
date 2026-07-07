"""
Reasoning Agent for complex analysis and escalation decisions.
Handles multi-step reasoning, policy interpretation, and risk assessment.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.rag import get_rag_engine
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


class EscalationLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ReasoningResult:
    """Result from reasoning agent."""

    answer: str
    reasoning_steps: List[str]
    recommendation: str
    escalation_level: EscalationLevel
    confidence: float
    risk_factors: List[str]
    next_steps: List[str]
    tokens_input: int = 0
    tokens_output: int = 0


class ReasoningAgent:
    """
    Agent for complex reasoning and decision making.
    """

    def __init__(self):
        self.client = get_claude_client()
        self.rag_engine = get_rag_engine()

    async def analyze(
        self,
        query: str,
        role: str = "support_engineer",
        context: Optional[Dict[str, Any]] = None,
    ) -> ReasoningResult:
        """
        Perform complex reasoning analysis.

        Args:
            query: User question
            role: User role
            context: Conversation context

        Returns:
            ReasoningResult
        """
        model_config = model_router.get_model_config("large")

        # Retrieve relevant documents for context
        rag_context, citations = await self.rag_engine.query(
            query=query,
            role=role,
            top_k=10,
            final_k=5,
        )

        # Build reasoning prompt
        prompt = self._build_reasoning_prompt(
            query=query,
            rag_context=rag_context,
            role=role,
            context=context,
        )

        try:
            response = await self.client.generate(
                model=model_config["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=model_config["max_tokens"],
                temperature=0.5,

            )

            # Parse response
            usage = response.get("usage", {})
            result = self._parse_reasoning_response(
                response["content"][0].text,
                citations,
            )
            result.tokens_input = usage.get("input_tokens", 0)
            result.tokens_output = usage.get("output_tokens", 0)

            return result

        except Exception as e:
            logger.error(f"Failed to perform reasoning: {e}")
            return self._fallback_reasoning(query)

    def _build_reasoning_prompt(
        self,
        query: str,
        rag_context: str,
        role: str,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """
        Build reasoning prompt.

        Args:
            query: User question
            rag_context: Retrieved context
            role: User role
            context: Conversation context

        Returns:
            Prompt string
        """
        role_guidance = self._get_role_guidance(role)

        return f"""
        {role_guidance}

        Perform detailed analysis and reasoning.

        Question: {query}

        Relevant Context:
        {rag_context}

        Conversation Context:
        {context or 'No additional context'}

        Please provide:
        1. Step-by-step reasoning
        2. Key considerations
        3. Recommendation
        4. Escalation level (none, low, medium, high, critical)
        5. Risk factors
        6. Next steps

        Return JSON with:
        - answer: Final answer
        - reasoning_steps: List of reasoning steps
        - recommendation: Clear recommendation
        - escalation_level: Escalation level
        - confidence: 0-1 score
        - risk_factors: List of risks
        - next_steps: List of next steps
        """

    def _get_role_guidance(self, role: str) -> str:
        """
        Get role-specific guidance.

        Args:
            role: User role

        Returns:
            Guidance string
        """
        guidance = {
            "support_engineer": """You are a support engineer. Focus on:
            - Customer satisfaction
            - Resolution efficiency
            - Escalation when needed
            - Policy compliance""",
            "mortgage_analyst": """You are a mortgage analyst. Focus on:
            - Loan eligibility
            - Risk assessment
            - Regulatory compliance
            - Financial accuracy""",
            "compliance_officer": """You are a compliance officer. Focus on:
            - Regulatory adherence
            - Audit trail completeness
            - Policy interpretation
            - Risk mitigation""",
            "product_owner": """You are a product owner. Focus on:
            - User needs
            - Feature requirements
            - Product strategy
            - User experience""",
        }
        return guidance.get(role, "Provide accurate, helpful analysis.")

    def _parse_reasoning_response(
        self,
        response_text: str,
        citations: List[Dict[str, Any]],
    ) -> ReasoningResult:
        """
        Parse reasoning response into structured result.

        Args:
            response_text: Raw LLM response
            citations: Document citations

        Returns:
            ReasoningResult
        """
        result = extract_json(response_text)

        if not isinstance(result, dict):
            # Fallback to simple parsing when no JSON is present
            return ReasoningResult(
                answer=response_text[:500] if len(response_text) > 500 else response_text,
                reasoning_steps=["Response parsed as text"],
                recommendation="Review the response for next steps",
                escalation_level=EscalationLevel.NONE,
                confidence=0.5,
                risk_factors=[],
                next_steps=["Review response", "Take appropriate action"],
            )

        # Parse escalation level
        escalation_str = result.get("escalation_level", "none")
        try:
            escalation_level = EscalationLevel(escalation_str)
        except ValueError:
            escalation_level = EscalationLevel.NONE

        return ReasoningResult(
            answer=result.get("answer", ""),
            reasoning_steps=result.get("reasoning_steps", []),
            recommendation=result.get("recommendation", ""),
            escalation_level=escalation_level,
            confidence=result.get("confidence", 0.8),
            risk_factors=result.get("risk_factors", []),
            next_steps=result.get("next_steps", []),
        )

    def _fallback_reasoning(self, query: str) -> ReasoningResult:
        """
        Fallback reasoning when LLM fails.

        Args:
            query: User question

        Returns:
            ReasoningResult
        """
        return ReasoningResult(
            answer="I'm experiencing technical difficulties. Please try again or contact support directly.",
            reasoning_steps=["System error occurred"],
            recommendation="Retry or contact support",
            escalation_level=EscalationLevel.MEDIUM,
            confidence=0.0,
            risk_factors=["System availability"],
            next_steps=["Retry query", "Contact technical support"],
        )

    def should_escalate(self, result: ReasoningResult) -> bool:
        """
        Determine if escalation is needed.

        Args:
            result: Reasoning result

        Returns:
            True if escalation needed
        """
        return result.escalation_level in [
            EscalationLevel.HIGH,
            EscalationLevel.CRITICAL,
        ]


# Global reasoning agent instance
reasoning_agent = ReasoningAgent()


def get_reasoning_agent() -> ReasoningAgent:
    """Get the global reasoning agent instance."""
    return reasoning_agent