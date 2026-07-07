"""
Summarization Agent for compressing long texts.
Handles customer emails, chat histories, and documents.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import logging

from app.config.llm_providers import get_claude_client, model_router
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


@dataclass
class SummaryResult:
    """Result from summarization agent."""

    summary: str
    key_points: List[str]
    action_items: List[str]
    sentiment: str
    confidence: float
    tokens_input: int = 0
    tokens_output: int = 0


class SummarizerAgent:
    """
    Agent for summarizing long texts.
    """

    def __init__(self):
        self.client = get_claude_client()

    async def summarize(
        self,
        text: str,
        max_length: int = 500,
        style: str = "concise",
        extract_key_points: bool = True,
    ) -> SummaryResult:
        """
        Summarize text.

        Args:
            text: Text to summarize
            max_length: Maximum summary length in characters
            style: concise, detailed, bullet_points
            extract_key_points: Whether to extract key points

        Returns:
            SummaryResult
        """
        model_config = model_router.get_model_config("medium")

        # Truncate if too long
        if len(text) > 10000:
            text = text[:10000]

        # Build prompt based on style
        style_instructions = {
            "concise": "Provide a brief, concise summary.",
            "detailed": "Provide a detailed summary with all important points.",
            "bullet_points": "Summarize as bullet points.",
        }

        prompt = f"""
        {style_instructions.get(style, style_instructions["concise"])}

        Text to summarize:
        {text}

        Return JSON with:
        - summary: The summarized text
        - key_points: List of key points (if extract_key_points)
        - action_items: List of action items mentioned
        - sentiment: customer sentiment (positive, neutral, negative, urgent)
        - confidence: 0-1 score of summary quality
        """

        try:
            response = await self.client.generate(
                model=model_config["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_length // 2,  # Rough token estimate
                temperature=0.3,
            )

            content = response["content"][0].text
            usage = response.get("usage", {})

            # Parse JSON response (tolerant of fences / trailing prose)
            result = extract_json(content, {})
            if not isinstance(result, dict):
                raise ValueError("LLM did not return JSON")

            return SummaryResult(
                summary=result.get("summary", ""),
                key_points=result.get("key_points", []),
                action_items=result.get("action_items", []),
                sentiment=result.get("sentiment", "neutral"),
                confidence=result.get("confidence", 0.8),
                tokens_input=usage.get("input_tokens", 0),
                tokens_output=usage.get("output_tokens", 0),
            )

        except Exception as e:
            logger.error(f"Failed to summarize text: {e}")
            return SummaryResult(
                summary=text[:max_length] if len(text) > max_length else text,
                key_points=[],
                action_items=[],
                sentiment="neutral",
                confidence=0.0,
            )

    async def summarize_conversation(
        self,
        conversation_history: List[Dict[str, str]],
        user_goal: Optional[str] = None,
    ) -> SummaryResult:
        """
        Summarize a conversation history.

        Args:
            conversation_history: List of {role, content} dicts
            user_goal: User's goal (if known)

        Returns:
            SummaryResult
        """
        # Build conversation text
        conversation_text = "\n".join([
            f"{t['role'].upper()}: {t['content'][:500]}"
            for t in conversation_history
        ])

        prompt = f"""
        Summarize this conversation, focusing on the user's goal and key decisions made.

        Conversation:
        {conversation_text}

        User Goal: {user_goal or "Not specified"}

        Return JSON with:
        - summary: Brief summary
        - key_points: Key points from conversation
        - action_items: Actions to take
        - sentiment: Overall sentiment
        - confidence: 0-1 score
        """

        try:
            response = await self.client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )

            content = response["content"][0].text
            result = extract_json(content, {})
            if not isinstance(result, dict):
                raise ValueError("LLM did not return JSON")

            return SummaryResult(
                summary=result.get("summary", ""),
                key_points=result.get("key_points", []),
                action_items=result.get("action_items", []),
                sentiment=result.get("sentiment", "neutral"),
                confidence=result.get("confidence", 0.8),
            )

        except Exception as e:
            logger.error(f"Failed to summarize conversation: {e}")
            return SummaryResult(
                summary="Unable to summarize conversation.",
                key_points=[],
                action_items=[],
                sentiment="neutral",
                confidence=0.0,
            )


# Global summarizer agent instance
summarizer_agent = SummarizerAgent()


def get_summarizer_agent() -> SummarizerAgent:
    """Get the global summarizer agent instance."""
    return summarizer_agent