"""
Memory agents for updating STM and LTM.
Extracts facts, preferences, and decisions from conversations.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging
import re

from app.config.llm_providers import get_claude_client, model_router
from app.memory.ltm import LTMManager
from app.memory.stm import STMManager
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


@dataclass
class ExtractedFact:
    """Extracted fact from conversation."""
    key: str
    value: str
    confidence: float = 0.8
    source_turn: int = 0


@dataclass
class ExtractedPreference:
    """Extracted user preference."""
    key: str
    value: str
    type: str = "string"


@dataclass
class ExtractedDecision:
    """Extracted decision from conversation."""
    description: str
    outcome: str
    timestamp: str


class MemoryAgent:
    """
    Agent that extracts and stores information in memory.
    Updates both STM and LTM with relevant information.
    """

    def __init__(
        self,
        stm_manager: Optional[STMManager] = None,
        ltm_manager: Optional[LTMManager] = None,
    ):
        self.stm = stm_manager
        self.ltm = ltm_manager or LTMManager()
        self.client = get_claude_client()

    async def extract_and_store(
        self,
        session_id: str,
        user_id: str,
        conversation_turns: List[Dict[str, str]],
        role: str,
    ) -> Dict[str, Any]:
        """
        Extract information from conversation and store in memory.

        Args:
            session_id: Session ID
            user_id: User ID
            conversation_turns: List of conversation turns
            role: User role

        Returns:
            Summary of extracted information
        """
        if not conversation_turns:
            return {"facts_extracted": 0, "preferences_extracted": 0}

        # Extract information using LLM
        extracted = await self._extract_information(conversation_turns, role)

        # Store in LTM
        stored = {
            "facts": 0,
            "preferences": 0,
            "decisions": 0,
        }

        for fact in extracted.facts:
            await self.ltm.store_fact(
                user_id=user_id,
                fact_key=fact.key,
                fact_value=fact.value,
                metadata={"confidence": fact.confidence, "source": "conversation"},
            )
            stored["facts"] += 1

        for pref in extracted.preferences:
            await self.ltm.store_preference(
                user_id=user_id,
                preference_key=pref.key,
                preference_value=pref.value,
                metadata={"type": pref.type},
            )
            stored["preferences"] += 1

        logger.info(f"Memory agent extracted: {stored}")

        return stored

    async def _extract_information(
        self,
        turns: List[Dict[str, str]],
        role: str,
    ) -> "ExtractedInformation":
        """
        Extract facts, preferences, and decisions from conversation.

        Args:
            turns: Conversation turns
            role: User role

        Returns:
            ExtractedInformation object
        """
        # Build conversation text
        conversation_text = "\n".join([
            f"{t['role'].upper()}: {t['content']}"
            for t in turns[-10:]  # Last 10 turns
        ])

        prompt = f"""
        Analyze this conversation and extract:

        Conversation:
        {conversation_text}

        Role: {role}

        Extract and return JSON with:
        - facts: List of {{key, value, confidence}} - important facts mentioned
        - preferences: List of {{key, value, type}} - user preferences/stated needs
        - decisions: List of {{description, outcome}} - decisions made

        Only extract concrete information, not assumptions.
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.2,
            )

            content = response["content"][0].text
            data = extract_json(content, {})

            facts = [
                ExtractedFact(
                    key=f.get("key", ""),
                    value=f.get("value", ""),
                    confidence=f.get("confidence", 0.8),
                )
                for f in data.get("facts", [])
            ]

            preferences = [
                ExtractedPreference(
                    key=p.get("key", ""),
                    value=p.get("value", ""),
                    type=p.get("type", "string"),
                )
                for p in data.get("preferences", [])
            ]

            decisions = [
                ExtractedDecision(
                    description=d.get("description", ""),
                    outcome=d.get("outcome", ""),
                )
                for d in data.get("decisions", [])
            ]

            return ExtractedInformation(facts=facts, preferences=preferences, decisions=decisions)

        except Exception as e:
            logger.error(f"Failed to extract information: {e}")
            return ExtractedInformation(facts=[], preferences=[], decisions=[])


@dataclass
class ExtractedInformation:
    """Container for extracted information."""
    facts: List[ExtractedFact] = field(default_factory=list)
    preferences: List[ExtractedPreference] = field(default_factory=list)
    decisions: List[ExtractedDecision] = field(default_factory=list)


class FactExtractor:
    """
    Rule-based fact extractor for common patterns.
    Used as a fallback when LLM extraction fails.
    """

    # Common patterns for fact extraction
    PATTERNS = {
        "customer_id": r"(?:customer|client|account)\s*(?:id|number|#|id\.?)\s*[:=]?\s*([A-Z0-9-]{5,20})",
        "ticket_number": r"(?:ticket|case|issue)\s*(?:number|#|id\.?)\s*[:=]?\s*([A-Z0-9]{5,20})",
        "date": r"(\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    }

    def extract_facts(self, text: str) -> List[ExtractedFact]:
        """
        Extract facts using regex patterns.

        Args:
            text: Text to extract from

        Returns:
            List of extracted facts
        """
        facts = []

        for fact_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match[0] else match[1] if len(match) > 1 else match
                facts.append(ExtractedFact(
                    key=fact_type,
                    value=match,
                    confidence=0.9,
                ))

        return facts

    def extract_preferences(self, text: str, role: str) -> List[ExtractedPreference]:
        """
        Extract user preferences from text.

        Args:
            text: Text to extract from
            role: User role

        Returns:
            List of extracted preferences
        """
        preferences = []

        # Role-specific patterns
        role_patterns = {
            "support_engineer": ["escalation", "priority", "sla", "response time"],
            "mortgage_analyst": ["loan type", "interest rate", "down payment", "term"],
            "compliance_officer": ["policy", "regulation", "audit", "review"],
            "product_owner": ["feature", "requirement", "priority", "deadline"],
        }

        keywords = role_patterns.get(role, [])

        for keyword in keywords:
            # Look for "I need" or "user wants" patterns
            pattern = rf"(?:i|the user|customer) (?:need|wants|requires?)\s+(?:the\s+)?{keyword}[^.,;]*[.,;]"
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                preferences.append(ExtractedPreference(
                    key=f"preference_{keyword.replace(' ', '_')}",
                    value=match.strip(),
                    type="string",
                ))

        return preferences


# Global memory agent instance
memory_agent: Optional[MemoryAgent] = None


def get_memory_agent() -> MemoryAgent:
    """Get or create the global memory agent instance."""
    global memory_agent
    if memory_agent is None:
        memory_agent = MemoryAgent()
    return memory_agent