"""
Memory Agent for updating STM and LTM.
Extracts facts, preferences, and decisions from conversations.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.memory.ltm import LTMManager
from app.memory.stm import STMManager
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


@dataclass
class MemoryUpdateResult:
    """Result of memory update operation."""

    facts_extracted: int
    preferences_extracted: int
    decisions_recorded: int
    ltm_vectors_added: int


class MemoryAgent:
    """
    Agent that updates short-term and long-term memory.
    """

    def __init__(
        self,
        stm_manager: Optional[STMManager] = None,
        ltm_manager: Optional[LTMManager] = None,
    ):
        self.stm = stm_manager
        self.ltm = ltm_manager or LTMManager()
        self.client = get_claude_client()

    async def update_memory(
        self,
        session_id: str,
        user_id: str,
        conversation_turns: List[Dict[str, str]],
        role: str,
    ) -> MemoryUpdateResult:
        """
        Update memory with conversation information.

        Args:
            session_id: Session ID
            user_id: User ID
            conversation_turns: List of conversation turns
            role: User role

        Returns:
            MemoryUpdateResult
        """
        if not conversation_turns:
            return MemoryUpdateResult(0, 0, 0, 0)

        # Extract information from conversation
        extracted = await self._extract_information(conversation_turns, role)

        # Update LTM with facts
        facts_added = 0
        for fact in extracted.get("facts", []):
            await self.ltm.store_fact(
                user_id=user_id,
                fact_key=fact["key"],
                fact_value=fact["value"],
                metadata={"source": "conversation", "confidence": fact.get("confidence", 0.8)},
            )
            facts_added += 1

        # Update LTM with preferences
        preferences_added = 0
        for pref in extracted.get("preferences", []):
            await self.ltm.store_preference(
                user_id=user_id,
                preference_key=pref["key"],
                preference_value=pref["value"],
                metadata={"type": pref.get("type", "string")},
            )
            preferences_added += 1

        # Record decisions
        decisions_recorded = 0
        for decision in extracted.get("decisions", []):
            # Store decision in LTM
            await self.ltm.store_fact(
                user_id=user_id,
                fact_key=f"decision_{int(decision.get('timestamp', 0))}",
                fact_value=decision["description"],
                metadata={
                    "outcome": decision.get("outcome", ""),
                    "source": "decision",
                },
            )
            decisions_recorded += 1

        logger.info(f"Memory updated: {facts_added} facts, {preferences_added} prefs, {decisions_recorded} decisions")

        return MemoryUpdateResult(
            facts_extracted=facts_added,
            preferences_extracted=preferences_added,
            decisions_recorded=decisions_recorded,
            ltm_vectors_added=facts_added + preferences_added,
        )

    async def _extract_information(
        self,
        turns: List[Dict[str, str]],
        role: str,
    ) -> Dict[str, Any]:
        """
        Extract information from conversation turns.

        Args:
            turns: Conversation turns
            role: User role

        Returns:
            Dict with extracted information
        """
        # Build conversation text
        conversation_text = "\n".join([
            f"{t['role'].upper()}: {t['content']}"
            for t in turns[-10:]  # Last 10 turns
        ])

        prompt = f"""
        Extract structured information from this conversation:

        Conversation:
        {conversation_text}

        Role: {role}

        Extract ONLY concrete, verifiable information:
        - facts: Key facts mentioned (customer needs, issues, preferences)
        - preferences: User preferences or stated needs
        - decisions: Decisions made during conversation

        Return JSON with these three lists. Empty lists if nothing found.
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.2,
            )

            content = response["content"][0].text
            return extract_json(content, {"facts": [], "preferences": [], "decisions": []})

        except Exception as e:
            logger.error(f"Failed to extract information: {e}")
            return {"facts": [], "preferences": [], "decisions": []}

    async def get_user_profile(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get user profile from LTM.

        Args:
            user_id: User ID

        Returns:
            User profile dict
        """
        return await self.ltm.get_user_profile(user_id)

    async def search_memory(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search user's memory for relevant information.

        Args:
            user_id: User ID
            query: Search query
            top_k: Number of results

        Returns:
            List of relevant memories
        """
        facts = await self.ltm.retrieve_facts(user_id, query, top_k)
        preferences = await self.ltm.retrieve_preferences(user_id, query, top_k)

        return {
            "facts": facts,
            "preferences": preferences,
        }


# Global memory agent instance
memory_agent = MemoryAgent()


def get_memory_agent() -> MemoryAgent:
    """Get the global memory agent instance."""
    return memory_agent