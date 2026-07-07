"""
Context compression utilities for memory management.
Implements summarization, semantic memory, and role-based filtering.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


@dataclass
class ConversationSummary:
    """Structured conversation summary."""

    user_goals: List[str] = field(default_factory=list)
    decisions_made: List[Dict[str, Any]] = field(default_factory=list)
    key_facts: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    previous_context: str = ""


@dataclass
class CompressedContext:
    """Compressed context for model input."""

    user_goal: str = ""
    key_facts: str = ""
    relevant_docs: str = ""
    constraints: str = ""
    previous_decisions: str = ""
    recent_turns: str = ""


class ContextCompressor:
    """
    Compresses conversation context using multiple techniques:
    - Summarization of history
    - Semantic memory extraction
    - Role-based filtering
    - Template-based structuring
    """

    def __init__(self):
        self.client = get_claude_client()

    async def summarize_conversation(
        self,
        conversation_history: List[Dict[str, str]],
        max_summary_tokens: int = 500,
    ) -> ConversationSummary:
        """
        Summarize conversation history into structured format.

        Args:
            conversation_history: List of {role, content} dicts
            max_summary_tokens: Maximum tokens for summary

        Returns:
            ConversationSummary object
        """
        if not conversation_history:
            return ConversationSummary()

        # Build conversation text
        conversation_text = "\n".join([
            f"{turn['role'].upper()}: {turn['content'][:500]}"
            for turn in conversation_history[-20:]  # Limit to last 20 turns
        ])

        prompt = f"""
        Analyze this conversation and extract structured information:

        Conversation:
        {conversation_text}

        Return a JSON object with:
        - user_goals: List of what the user wants to achieve
        - decisions_made: List of decisions made during conversation
        - key_facts: Dictionary of important facts extracted
        - constraints: Dictionary of constraints mentioned

        Format as valid JSON only.
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_summary_tokens,
                temperature=0.3,
            )

            content = response["content"][0].text
            summary_dict = extract_json(content, {})

            return ConversationSummary(
                user_goals=summary_dict.get("user_goals", []),
                decisions_made=summary_dict.get("decisions_made", []),
                key_facts=summary_dict.get("key_facts", {}),
                constraints=summary_dict.get("constraints", {}),
            )

        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return ConversationSummary()

    async def compress_rag_context(
        self,
        chunks: List[Dict[str, Any]],
        query: str,
        role: str,
    ) -> str:
        """
        Compress RAG chunks into a concise context.

        Args:
            chunks: List of retrieved chunks with metadata
            query: Original query
            role: User role for filtering

        Returns:
            Compressed context string
        """
        if not chunks:
            return ""

        # Filter by role if needed
        filtered_chunks = self._filter_by_role(chunks, role)

        # Select top chunks
        top_chunks = filtered_chunks[:5]

        # Build compressed context
        context_parts = []

        for i, chunk in enumerate(top_chunks, 1):
            # Extract key fields
            title = chunk.get("title", "Document")
            content = chunk.get("content", "")
            source = chunk.get("source", "Unknown")

            # Summarize chunk if too long
            if len(content) > 500:
                content = await self._summarize_chunk(content)

            context_parts.append(f"[{i}] {title} (Source: {source})\n{content}")

        return "\n\n".join(context_parts)

    async def _summarize_chunk(self, content: str) -> str:
        """
        Summarize a document chunk.

        Args:
            content: Chunk content

        Returns:
            Summarized content
        """
        prompt = f"""
        Summarize the following text to its key points:

        {content[:1000]}

        Return a concise summary focusing on key facts and actionable information.
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3,
            )
            return response["content"][0].text
        except Exception:
            return content[:300] + "..."

    def _filter_by_role(self, chunks: List[Dict[str, Any]], role: str) -> List[Dict[str, Any]]:
        """
        Filter chunks by role-based access.

        Args:
            chunks: List of chunks
            role: User role

        Returns:
            Filtered chunks
        """
        from app.config.pinecone_client import NAMESPACES

        role_namespace = NAMESPACES["rag"].get(role, NAMESPACES["rag"]["global"])

        filtered = []
        for chunk in chunks:
            chunk_roles = chunk.get("metadata", {}).get("role_restriction", [])
            if not chunk_roles or role in chunk_roles or "global" in chunk_roles:
                filtered.append(chunk)

        return filtered if filtered else chunks

    def build_template_context(
        self,
        user_goal: str,
        key_facts: Dict[str, Any],
        relevant_docs: str,
        constraints: Dict[str, Any],
        previous_decisions: List[Dict[str, Any]],
        role: str,
    ) -> str:
        """
        Build structured context using templates.

        Args:
            user_goal: User's goal
            key_facts: Extracted facts
            relevant_docs: Relevant documents
            constraints: Constraints
            previous_decisions: Previous decisions
            role: User role

        Returns:
            Formatted context string
        """
        template = f"""
        CONTEXT FOR {role.upper()}:

        USER GOAL:
        {user_goal}

        KEY FACTS:
        {self._format_facts(key_facts)}

        RELEVANT DOCUMENTS:
        {relevant_docs if relevant_docs else "No relevant documents found."}

        CONSTRAINTS:
        {self._format_constraints(constraints)}

        PREVIOUS DECISIONS:
        {self._format_decisions(previous_decisions)}

        ROLE-SPECIFIC GUIDANCE:
        {self._get_role_guidance(role)}
        """
        return template.strip()

    def _format_facts(self, facts: Dict[str, Any]) -> str:
        """Format facts for display."""
        if not facts:
            return "No facts available."
        return "\n".join([f"- {k}: {v}" for k, v in facts.items()])

    def _format_constraints(self, constraints: Dict[str, Any]) -> str:
        """Format constraints for display."""
        if not constraints:
            return "No specific constraints."
        return "\n".join([f"- {k}: {v}" for k, v in constraints.items()])

    def _format_decisions(self, decisions: List[Dict[str, Any]]) -> str:
        """Format decisions for display."""
        if not decisions:
            return "No previous decisions."
        lines = []
        for d in decisions:
            lines.append(f"- {d.get('description', 'Decision')}: {d.get('outcome', 'Pending')}")
        return "\n".join(lines)

    def _get_role_guidance(self, role: str) -> str:
        """Get role-specific guidance."""
        guidance = {
            "support_engineer": "Focus on customer satisfaction, use KB articles, escalate if needed.",
            "mortgage_analyst": "Focus on regulatory compliance, risk assessment, loan terms.",
            "compliance_officer": "Focus on regulatory requirements, audit trails, policy adherence.",
            "product_owner": "Focus on user needs, feature requirements, roadmap alignment.",
        }
        return guidance.get(role, "Provide helpful, accurate information.")

    async def compress_full_context(
        self,
        conversation_history: List[Dict[str, str]],
        ltm_facts: List[Dict[str, Any]],
        ltm_preferences: List[Dict[str, Any]],
        rag_context: str,
        role: str,
    ) -> str:
        """
        Compress full context using all techniques.

        Args:
            conversation_history: Full conversation
            ltm_facts: Long-term memory facts
            ltm_preferences: User preferences
            rag_context: RAG document context
            role: User role

        Returns:
            Fully compressed context
        """
        # Summarize conversation
        summary = await self.summarize_conversation(conversation_history)

        # Build compressed context
        compressed = self.build_template_context(
            user_goal="\n".join(summary.user_goals) if summary.user_goals else "No specific goal stated.",
            key_facts=summary.key_facts,
            relevant_docs=rag_context,
            constraints=summary.constraints,
            previous_decisions=summary.decisions_made,
            role=role,
        )

        # Add LTM facts if available
        if ltm_facts:
            facts_text = "\n".join([
                f"- {f.get('fact_key', 'Fact')}: {f.get('fact_value', 'Unknown')}"
                for f in ltm_facts[:5]
            ])
            compressed += f"\n\nLONG-TERM MEMORY FACTS:\n{facts_text}"

        # Add preferences if available
        if ltm_preferences:
            prefs_text = "\n".join([
                f"- {p.get('key', 'Preference')}: {p.get('value', 'Unknown')}"
                for p in ltm_preferences[:3]
            ])
            compressed += f"\n\nUSER PREFERENCES:\n{prefs_text}"

        return compressed


# Global compressor instance
compressor = ContextCompressor()


def get_compressor() -> ContextCompressor:
    """Get the global context compressor instance."""
    return compressor