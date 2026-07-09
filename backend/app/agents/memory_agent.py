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
            if isinstance(fact, dict):
                key = fact.get("key")
                value = fact.get("value")
                confidence = fact.get("confidence", 0.8)
            else:
                # fact is a string
                key = str(fact)
                value = str(fact)
                confidence = 0.8
            if key is None or value is None:
                # skip if missing
                continue
            await self.ltm.store_fact(
                user_id=user_id,
                fact_key=key,
                fact_value=value,
                metadata={"source": "conversation", "confidence": confidence},
            )
            facts_added += 1

        # Update LTM with preferences
        preferences_added = 0
        for pref in extracted.get("preferences", []):
            if isinstance(pref, dict):
                key = pref.get("key")
                value = pref.get("value")
                ptype = pref.get("type", "string")
            else:
                key = str(pref)
                value = str(pref)
                ptype = "string"
            if key is None or value is None:
                continue
            await self.ltm.store_preference(
                user_id=user_id,
                preference_key=key,
                preference_value=value,
                metadata={"type": ptype},
            )
            preferences_added += 1

        # Record decisions
        decisions_recorded = 0
        for decision in extracted.get("decisions", []):
            if isinstance(decision, dict):
                description = decision.get("description")
                outcome = decision.get("outcome", "")
                timestamp = decision.get("timestamp")
            else:
                description = str(decision)
                outcome = ""
                timestamp = None
            if description is None:
                continue
            fact_key = f"decision_{timestamp}" if timestamp is not None else f"decision_{hash(description)}"
            await self.ltm.store_fact(
                user_id=user_id,
                fact_key=fact_key,
                fact_value=description,
                metadata={
                    "outcome": outcome,
                    "source": "decision",
                },
            )
            decisions_recorded += 1

        # Update STM with conversation turns
        if self.stm:
            await self.stm.add_conversation_turns(conversation_turns)

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
        Extract ONLY concrete, verifiable information from the conversation.
        Return a JSON object with three arrays: facts, preferences, decisions.

        Each fact should be an object with "key" (a short identifier) and "value" (the fact text).
        Each preference should be an object with "key" and "value".
        Each decision should be an object with "description" and optionally "outcome".

        Example:
        {{
          "facts": [{{"key": "customer_name", "value": "John Doe"}}],
          "preferences": [{{"key": "contact_method", "value": "email"}}],
          "decisions": [{{"description": "Escalate to supervisor", "outcome": "pending"}}]
        }}

        If no information is found, return empty arrays.

        Conversation:
        {conversation_text}

        Role: {role}
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