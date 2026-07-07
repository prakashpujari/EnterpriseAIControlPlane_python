"""
RAG Agent for document retrieval and answering.
Uses hybrid search with re-ranking and role-based filtering.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.rag import get_rag_engine

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """Result from RAG agent."""

    answer: str
    sources: List[Dict[str, str]]
    citations: List[Dict[str, Any]]
    confidence: float
    grounding_score: float
    tokens_input: int = 0
    tokens_output: int = 0


class RAGAgent:
    """
    Agent for answering questions using RAG.
    """

    def __init__(self):
        self.client = get_claude_client()
        self.rag_engine = get_rag_engine()

    async def answer_question(
        self,
        query: str,
        role: str = "support_engineer",
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> RAGResult:
        """
        Answer a question using RAG.

        Args:
            query: User question
            role: User role
            context: Conversation context
            top_k: Number of documents to retrieve

        Returns:
            RAGResult with answer and sources
        """
        # Retrieve relevant documents
        context_text, citations = await self.rag_engine.query(
            query=query,
            role=role,
            top_k=top_k,
            final_k=5,
        )

        # Generate answer with grounding
        answer = await self._generate_grounded_answer(
            query=query,
            context=context_text,
            role=role,
            citations=citations,
        )

        return RAGResult(
            answer=answer["answer"],
            sources=answer["sources"],
            citations=citations,
            confidence=answer["confidence"],
            grounding_score=answer["grounding_score"],
            tokens_input=answer.get("tokens_input", 0),
            tokens_output=answer.get("tokens_output", 0),
        )

    async def _generate_grounded_answer(
        self,
        query: str,
        context: str,
        role: str,
        citations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Generate a grounded answer using retrieved context.

        Args:
            query: User question
            context: Retrieved document context
            role: User role
            citations: Document citations

        Returns:
            Dict with answer and metadata
        """
        model_config = model_router.get_model_config("medium")

        # Build prompt
        prompt = f"""
        Answer the following question using ONLY the provided context.
        Cite specific sources using [1], [2], etc.

        Context:
        {context}

        Question: {query}

        Role: {role}

        Guidelines:
        1. Base your answer ONLY on the provided context
        2. Cite sources using [1], [2], etc.
        3. If information is not in context, say "I don't have that information in my documents"
        4. Be concise but thorough

        Answer:
        """

        try:
            response = await self.client.generate(
                model=model_config["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=model_config["max_tokens"],
                temperature=0.3,
            )

            answer_text = response["content"][0].text
            usage = response.get("usage", {})

            # Calculate grounding score (simplified)
            grounding_score = self._calculate_grounding_score(answer_text, citations)

            # Extract sources
            sources = [
                {
                    "title": c["title"],
                    "source": c["source"],
                    "url": c.get("url", ""),
                }
                for c in citations
            ]

            return {
                "answer": answer_text,
                "sources": sources,
                "confidence": 0.9 if grounding_score > 0.7 else 0.7,
                "grounding_score": grounding_score,
                "tokens_input": usage.get("input_tokens", 0),
                "tokens_output": usage.get("output_tokens", 0),
            }

        except Exception as e:
            logger.error(f"Failed to generate RAG answer: {e}")
            return {
                "answer": "I apologize, but I'm unable to retrieve information at this time.",
                "sources": [],
                "confidence": 0.0,
                "grounding_score": 0.0,
            }

    def _calculate_grounding_score(self, answer: str, citations: List[Dict]) -> float:
        """
        Calculate grounding score based on citations in answer.

        Args:
            answer: Generated answer
            citations: Available citations

        Returns:
            Grounding score (0-1)
        """
        import re

        # Count citations in answer
        citation_pattern = r'\[\d+\]'
        citations_in_answer = len(re.findall(citation_pattern, answer))

        # Count available citations
        total_citations = len(citations)

        if total_citations == 0:
            return 0.0

        # Score based on citation usage
        score = min(1.0, citations_in_answer / total_citations)

        return score


# Global RAG agent instance
rag_agent = RAGAgent()


def get_rag_agent() -> RAGAgent:
    """Get the global RAG agent instance."""
    return rag_agent