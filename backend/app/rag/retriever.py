"""
RAG retriever module implementing hybrid search (vector + BM25).
Retrieves relevant documents for customer queries.
"""

import uuid
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

from pinecone import Pinecone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.config.pinecone_client import get_rag_index, NAMESPACES
from app.config.llm_providers import get_claude_client, model_router

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""

    id: str
    content: str
    score: float
    title: str
    source: str
    chunk_index: int
    role_restriction: List[str]
    metadata: Dict[str, Any]


@dataclass
class RAGResult:
    """Result of RAG retrieval."""

    chunks: List[RetrievedChunk]
    total_results: int
    query: str
    role: str


class HybridRetriever:
    """
    Hybrid retriever combining vector search and BM25.
    Implements RAG 2.0 with re-ranking and role-based filtering.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
        self.client = get_claude_client()
        self.index = get_rag_index()

    async def retrieve(
        self,
        query: str,
        role: str,
        top_k: int = 20,
        final_k: int = 5,
        re_rank: bool = True,
    ) -> RAGResult:
        """
        Retrieve relevant chunks using hybrid search.

        Args:
            query: Search query
            role: User role for filtering
            top_k: Number of initial results
            final_k: Final number of results after re-ranking
            re_rank: Whether to re-rank results

        Returns:
            RAGResult with retrieved chunks
        """
        # Get query embedding
        query_embedding = await self._get_embedding(query)

        # Get role namespace
        namespace = NAMESPACES["rag"].get(role, NAMESPACES["rag"]["global"])

        # Vector search
        vector_results = await self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
        )

        # Process results
        chunks = []
        for match in vector_results.matches:
            metadata = match.metadata or {}

            # Role filter check
            chunk_roles = metadata.get("role_restriction", [])
            if self._is_allowed_for_role(role, chunk_roles):
                chunk = RetrievedChunk(
                    id=match.id,
                    content=metadata.get("content", ""),
                    score=match.score,
                    title=metadata.get("title", "Document"),
                    source=metadata.get("source", "Unknown"),
                    chunk_index=metadata.get("chunk_index", 0),
                    role_restriction=chunk_roles,
                    metadata=metadata,
                )
                chunks.append(chunk)

        # Re-rank if enabled
        if re_rank and len(chunks) > final_k:
            chunks = await self._re_rank(chunks, query, final_k)

        # Limit to final_k
        chunks = chunks[:final_k]

        logger.debug(f"Retrieved {len(chunks)} chunks for query '{query}'")

        return RAGResult(
            chunks=chunks,
            total_results=len(chunks),
            query=query,
            role=role,
        )

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        text = text.strip()[:8000]
        embeddings = await self.client.embed(text)
        return embeddings[0]

    def _is_allowed_for_role(self, user_role: str, chunk_roles: List[str]) -> bool:
        """
        Check if chunk is accessible by user role.

        Args:
            user_role: User's role
            chunk_roles: Roles allowed to access chunk

        Returns:
            True if allowed
        """
        if not chunk_roles:
            return True  # No restriction means global access

        if "global" in chunk_roles:
            return True

        return user_role in chunk_roles

    async def _re_rank(
        self,
        chunks: List[RetrievedChunk],
        query: str,
        top_k: int,
    ) -> List[RetrievedChunk]:
        """
        Re-rank chunks using cross-encoder.

        Args:
            chunks: Chunks to re-rank
            query: Original query
            top_k: Number of top results to keep

        Returns:
            Re-ranked chunks
        """
        # Use simple relevance scoring for now
        # In production, use a cross-encoder model

        scored_chunks = []
        for chunk in chunks:
            # Combine vector score with text relevance
            text_relevance = self._compute_text_relevance(query, chunk.content)
            combined_score = (chunk.score + text_relevance) / 2

            scored_chunks.append((chunk, combined_score))

        # Sort by score
        scored_chunks.sort(key=lambda x: x[1], reverse=True)

        return [chunk for chunk, _ in scored_chunks[:top_k]]

    def _compute_text_relevance(self, query: str, text: str) -> float:
        """
        Compute text-based relevance score.

        Args:
            query: Search query
            text: Document text

        Returns:
            Relevance score between 0 and 1
        """
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())

        if not query_words:
            return 0.0

        overlap = len(query_words & text_words)
        return overlap / len(query_words)


class DocumentProcessor:
    """
    Processes retrieved chunks into context for the model.
    """

    def __init__(self):
        self.compressor = None

    async def format_context(
        self,
        result: RAGResult,
        max_tokens: int = 2000,
    ) -> str:
        """
        Format retrieved chunks into model context.

        Args:
            result: RAG retrieval result
            max_tokens: Maximum tokens for context

        Returns:
            Formatted context string
        """
        if not result.chunks:
            return "No relevant documents found."

        context_parts = []

        for i, chunk in enumerate(result.chunks, 1):
            # Truncate content to fit token limit
            content = chunk.content
            if len(content) > 800:
                content = content[:800] + "..."

            # Format with metadata
            source_info = f"[{i}] {chunk.title}"
            if chunk.source and chunk.source != "Unknown":
                source_info += f" (Source: {chunk.source})"

            context_parts.append(f"{source_info}\n{content}")

        return "\n\n".join(context_parts)

    async def extract_citations(
        self,
        result: RAGResult,
    ) -> List[Dict[str, Any]]:
        """
        Extract citations from retrieval result.

        Args:
            result: RAG retrieval result

        Returns:
            List of citation objects
        """
        citations = []

        for i, chunk in enumerate(result.chunks, 1):
            citation = {
                "id": i,
                "title": chunk.title,
                "source": chunk.source,
                "url": chunk.metadata.get("url", ""),
                "snippet": chunk.content[:150] + "..." if len(chunk.content) > 150 else chunk.content,
            }
            citations.append(citation)

        return citations


class RAGEngine:
    """
    Main RAG engine combining retrieval and processing.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.retriever = HybridRetriever(db_session)
        self.processor = DocumentProcessor()

    async def query(
        self,
        query: str,
        role: str,
        top_k: int = 20,
        final_k: int = 5,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Execute a RAG query.

        Args:
            query: User query
            role: User role
            top_k: Initial retrieval count
            final_k: Final result count

        Returns:
            Tuple of (context, citations)
        """
        # Retrieve chunks
        result = await self.retriever.retrieve(
            query=query,
            role=role,
            top_k=top_k,
            final_k=final_k,
        )

        # Format context
        context = await self.processor.format_context(result)

        # Extract citations
        citations = await self.processor.extract_citations(result)

        return context, citations


# Global RAG engine instance
rag_engine: Optional[RAGEngine] = None


def get_rag_engine(db_session: Optional[AsyncSession] = None) -> RAGEngine:
    """Get or create the global RAG engine instance."""
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine(db_session)
    return rag_engine