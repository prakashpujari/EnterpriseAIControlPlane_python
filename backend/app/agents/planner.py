"""
Planner Agent for query classification and tool selection.
Decides which worker agents to invoke based on query type and role.
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.config.settings import QueryType
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


class QueryType(str, Enum):
    """Types of queries the system can handle."""
    FAQ = "faq"
    RAG = "rag"
    SUMMARIZE = "summarize"
    REASON = "reason"
    UNKNOWN = "unknown"


@dataclass
class PlannerResult:
    """Result from the planner agent."""

    query_type: QueryType
    confidence: float
    selected_tools: List[str]
    reasoning: str
    complexity: str  # low, medium, high
    recommended_model_tier: str


class PlannerAgent:
    """
    Analyzes user queries and determines the appropriate processing path.
    """

    # Keywords indicating FAQ-type queries
    FAQ_KEYWORDS = [
        "what are your hours",
        "when are you open",
        "how to contact",
        "phone number",
        "email address",
        "refund policy",
        "return policy",
        "shipping policy",
        "privacy policy",
        "terms of service",
        "account",
        "login",
        "password",
    ]

    # Keywords indicating RAG needs
    RAG_KEYWORDS = [
        "document",
        "policy",
        "manual",
        "procedure",
        "guideline",
        "regulation",
        "specification",
        "standard",
        "protocol",
    ]

    # Keywords indicating summarization needs
    SUMMARIZE_KEYWORDS = [
        "summarize",
        "summary",
        "brief",
        "condense",
        "key points",
        "main points",
        "essence",
    ]

    # Keywords indicating complex reasoning
    REASON_KEYWORDS = [
        "should i",
        "escalate",
        "recommend",
        "advice",
        "analysis",
        "evaluate",
        "compare",
        "risk",
        "impact",
        "consequence",
    ]

    def __init__(self):
        self.client = get_claude_client()

    async def classify_query(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        role: str = "support_engineer",
    ) -> PlannerResult:
        """
        Classify a query and select appropriate tools.

        Args:
            query: User query
            context: Optional conversation context
            role: User role

        Returns:
            PlannerResult with classification and tool selection
        """
        # First try rule-based classification
        rule_result = self._rule_based_classify(query, role)

        # Then refine with LLM if confidence is low
        if rule_result.confidence < 0.8:
            llm_result = await self._llm_classify(query, context, role)
            if llm_result.confidence > rule_result.confidence:
                return llm_result

        return rule_result

    def _rule_based_classify(
        self,
        query: str,
        role: str,
    ) -> PlannerResult:
        """
        Rule-based query classification.

        Args:
            query: User query
            role: User role

        Returns:
            PlannerResult
        """
        query_lower = query.lower()

        # Check FAQ keywords
        faq_matches = sum(1 for kw in self.FAQ_KEYWORDS if kw in query_lower)
        rag_matches = sum(1 for kw in self.RAG_KEYWORDS if kw in query_lower)
        summarize_matches = sum(1 for kw in self.SUMMARIZE_KEYWORDS if kw in query_lower)
        reason_matches = sum(1 for kw in self.REASON_KEYWORDS if kw in query_lower)

        scores = {
            QueryType.FAQ: faq_matches,
            QueryType.RAG: rag_matches,
            QueryType.SUMMARIZE: summarize_matches,
            QueryType.REASON: reason_matches,
        }

        # Determine query type
        query_type = max(scores, key=scores.get)
        confidence = min(0.9, scores[query_type] * 0.3 + 0.5)  # Scale confidence

        # Select tools based on query type
        tools = self._get_tools_for_type(query_type, role)

        # Determine complexity
        complexity = self._assess_complexity(query, query_type)

        # Get recommended model tier
        model_tier = model_router.route_query(
            query_type=query_type.value,
            role=role,
            complexity=complexity,
        )

        return PlannerResult(
            query_type=query_type,
            confidence=confidence,
            selected_tools=tools,
            reasoning=f"Rule-based classification: {query_type.value} (confidence: {confidence:.2f})",
            complexity=complexity,
            recommended_model_tier=model_tier,
        )

    async def _llm_classify(
        self,
        query: str,
        context: Optional[Dict[str, Any]],
        role: str,
    ) -> PlannerResult:
        """
        LLM-based query classification.

        Args:
            query: User query
            context: Conversation context
            role: User role

        Returns:
            PlannerResult
        """
        context_str = ""
        if context:
            context_str = f"\n\nContext: {str(context)[:500]}"

        prompt = f"""
        Classify this customer query into one of four categories:

        1. FAQ - Common question with known answer (hours, policies, how-to)
        2. RAG - Needs document retrieval (specific policy details, procedures)
        3. SUMMARIZE - Long text to summarize (forwarded emails, logs)
        4. REASON - Complex analysis needed (escalation, risk assessment)

        Query: "{query}"
        Role: {role}{context_str}

        Return ONLY valid JSON with:
        - query_type: one of FAQ, RAG, SUMMARIZE, REASON
        - confidence: 0-1 score
        - reasoning: brief explanation
        - complexity: low, medium, or high
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,  # Lower temperature for more deterministic JSON
            )

            content = response["content"][0].text

            # Robustly extract JSON (tolerates code fences / trailing prose)
            result = extract_json(content)
            if not isinstance(result, dict):
                raise ValueError("LLM did not return a JSON object")

            return PlannerResult(
                query_type=QueryType(result.get("query_type", "unknown").lower()),
                confidence=float(result.get("confidence", 0.5)),
                selected_tools=self._get_tools_for_type(
                    QueryType(result.get("query_type", "unknown").lower()),
                    role,
                ),
                reasoning=result.get("reasoning", ""),
                complexity=result.get("complexity", "medium"),
                recommended_model_tier=model_router.route_query(
                    query_type=result.get("query_type", "unknown").lower(),
                    role=role,
                    complexity=result.get("complexity", "medium"),
                ),
            )

        except Exception as e:
            logger.warning(f"LLM classification failed, using rule-based fallback: {e}")
            # Return rule-based fallback
            return self._rule_based_classify(query, role)

    def _get_tools_for_type(self, query_type: QueryType, role: str) -> List[str]:
        """
        Get appropriate tools for query type.

        Args:
            query_type: Type of query
            role: User role

        Returns:
            List of tool names
        """
        tools_by_type = {
            QueryType.FAQ: ["faq_search", "vector_search"],
            QueryType.RAG: ["hybrid_search", "bm25_search", "re_rank"],
            QueryType.SUMMARIZE: ["retrieve_history", "summarize_text"],
            QueryType.REASON: ["hybrid_search", "reasoning_chain", "tool_use"],
            QueryType.UNKNOWN: ["fallback"],
        }

        return tools_by_type.get(query_type, ["fallback"])

    def _assess_complexity(self, query: str, query_type: QueryType) -> str:
        """
        Assess query complexity.

        Args:
            query: User query
            query_type: Type of query

        Returns:
            Complexity level: low, medium, high
        """
        if query_type == QueryType.FAQ:
            return "low"

        # Check for complex indicators
        complex_indicators = [
            "escalate", "recommend", "analyze", "evaluate", "compare",
            "risk", "impact", "consequence", "multiple scenarios",
            "what if", "how should i", "best approach",
        ]

        query_lower = query.lower()
        complex_count = sum(1 for ind in complex_indicators if ind in query_lower)

        if complex_count >= 2:
            return "high"
        elif complex_count == 1:
            return "medium"
        else:
            return "low"


# Global planner instance
planner = PlannerAgent()


def get_planner() -> PlannerAgent:
    """Get the global planner agent instance."""
    return planner