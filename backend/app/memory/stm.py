"""
Short-term Memory (STM) implementation.
Stores recent conversation turns in PostgreSQL and compresses older turns into summaries.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, insert, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging

from app.models.database import (
    ConversationSession,
    ConversationTurn,
    ConversationSummary,
)
from app.config.settings import settings
from app.config.llm_providers import get_claude_client, model_router
from app.utils.json_utils import extract_json

logger = logging.getLogger(__name__)


class STMManager:
    """
    Short-term Memory Manager.
    Manages recent conversation turns and their compression.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.max_turns = settings.STM_MAX_TURNS
        self.summary_threshold = settings.STM_SUMMARY_THRESHOLD

    async def create_session(
        self,
        user_id: Optional[str],
        role: str,
        title: Optional[str] = None,
    ) -> str:
        """
        Create a new conversation session.

        Args:
            user_id: User ID
            role: User role
            title: Optional session title

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())

        stmt = insert(ConversationSession).values(
            id=session_id,
            user_id=user_id,
            role=role,
            title=title or f"Chat Session - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )

        await self.db.execute(stmt)
        await self.db.commit()

        logger.info(f"Created session {session_id} for role {role}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get a conversation session with its turns.

        Args:
            session_id: Session ID

        Returns:
            ConversationSession or None
        """
        stmt = (
            select(ConversationSession)
            .options(selectinload(ConversationSession.turns))
            .where(ConversationSession.id == session_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        model_used: Optional[str] = None,
        tokens_used: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a conversation turn.

        Args:
            session_id: Session ID
            role: Turn role (user, assistant, system)
            content: Turn content
            model_used: Model used (for assistant turns)
            tokens_used: Tokens used
            metadata: Additional metadata

        Returns:
            Turn ID
        """
        # Get current turn count
        stmt = select(ConversationTurn).where(ConversationTurn.session_id == session_id)
        result = await self.db.execute(stmt)
        turns = result.scalars().all()
        turn_number = len(turns) + 1

        turn_id = str(uuid.uuid4())

        stmt = insert(ConversationTurn).values(
            id=turn_id,
            session_id=session_id,
            turn_number=turn_number,
            role=role,
            content=content,
            model_used=model_used,
            tokens_used=tokens_used,
            metadata=metadata or {},
        )

        await self.db.execute(stmt)
        await self.db.commit()

        # Check if we need to compress older turns
        if turn_number >= self.summary_threshold:
            await self._compress_old_turns(session_id)

        return turn_id

    async def get_recent_turns(
        self,
        session_id: str,
        n: Optional[int] = None,
    ) -> List[ConversationTurn]:
        """
        Get recent conversation turns.

        Args:
            session_id: Session ID
            n: Number of turns to retrieve (default: max_turns)

        Returns:
            List of ConversationTurn objects
        """
        if n is None:
            n = self.max_turns

        stmt = (
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.turn_number.desc())
            .limit(n)
            .order_by(ConversationTurn.turn_number.asc())
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_summarized_history(
        self,
        session_id: str,
    ) -> Tuple[List[ConversationTurn], Optional[ConversationSummary]]:
        """
        Get conversation history with summaries for older turns.

        Args:
            session_id: Session ID

        Returns:
            Tuple of (recent_turns, latest_summary)
        """
        # Get all turns
        stmt = (
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.turn_number.asc())
        )

        result = await self.db.execute(stmt)
        all_turns = result.scalars().all()

        # Get latest summary
        summary_stmt = (
            select(ConversationSummary)
            .where(ConversationSummary.session_id == session_id)
            .order_by(ConversationSummary.turn_range_end.desc())
            .limit(1)
        )

        summary_result = await self.db.execute(summary_stmt)
        latest_summary = summary_result.scalar_one_or_none()

        # Get recent turns (last N)
        recent_turns = all_turns[-self.max_turns:] if len(all_turns) > self.max_turns else all_turns

        return recent_turns, latest_summary

    async def _compress_old_turns(self, session_id: str) -> None:
        """
        Compress older turns into a summary.

        Args:
            session_id: Session ID
        """
        # Get all turns
        stmt = (
            select(ConversationTurn)
            .where(ConversationTurn.session_id == session_id)
            .order_by(ConversationTurn.turn_number.asc())
        )

        result = await self.db.execute(stmt)
        all_turns = result.scalars().all()

        if len(all_turns) <= self.summary_threshold:
            return

        # Get turns to summarize
        turns_to_summarize = all_turns[:-self.max_turns]

        if not turns_to_summarize:
            return

        # Create conversation text for summarization
        conversation_text = "\n".join([
            f"{t.role.upper()}: {t.content}"
            for t in turns_to_summarize
        ])

        # Summarize using LLM
        summary = await self._summarize_turns(conversation_text)

        if summary:
            # Create summary record
            summary_id = str(uuid.uuid4())
            first_turn_num = turns_to_summarize[0].turn_number
            last_turn_num = turns_to_summarize[-1].turn_number

            stmt = insert(ConversationSummary).values(
                id=summary_id,
                session_id=session_id,
                turn_range_start=first_turn_num,
                turn_range_end=last_turn_num,
                user_goals=summary.get("user_goals", []),
                decisions_made=summary.get("decisions_made", []),
                key_facts=summary.get("key_facts", {}),
                constraints=summary.get("constraints", {}),
            )

            await self.db.execute(stmt)
            await self.db.commit()

            logger.info(f"Created summary for turns {first_turn_num}-{last_turn_num}")

            # Delete summarized turns
            delete_stmt = (
                delete(ConversationTurn)
                .where(ConversationTurn.session_id == session_id)
                .where(ConversationTurn.turn_number <= last_turn_num)
            )
            await self.db.execute(delete_stmt)
            await self.db.commit()

    async def _summarize_turns(self, conversation_text: str) -> Optional[Dict[str, Any]]:
        """
        Summarize conversation turns using LLM.

        Args:
            conversation_text: Text of turns to summarize

        Returns:
            Summary dict with goals, facts, decisions, constraints
        """
        client = get_claude_client()

        prompt = f"""
        Summarize the following conversation into structured information:

        Conversation:
        {conversation_text[:4000]}

        Extract and return a JSON object with:
        - user_goals: List of user goals expressed
        - decisions_made: List of key decisions made
        - key_facts: Dictionary of important facts
        - constraints: Dictionary of constraints mentioned

        Format as valid JSON only, no markdown.
        """

        try:
            response = await client.generate(
                model=model_router.get_model_config("small")["model"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.3,
            )

            content = response["content"][0].text
            summary = extract_json(content)
            return summary

        except Exception as e:
            logger.error(f"Failed to summarize turns: {e}")
            return None

    async def get_compressed_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get compressed context for a session.
        Combines recent turns with summaries and LTM facts.

        Args:
            session_id: Session ID

        Returns:
            Compressed context dict
        """
        # Get recent turns
        recent_turns, latest_summary = await self.get_summarized_history(session_id)

        # Format recent turns
        recent_turns_text = "\n".join([
            f"{t.role.upper()}: {t.content}"
            for t in recent_turns
        ])

        # Build context
        context = {
            "recent_turns": recent_turns_text,
            "summary": {
                "user_goals": latest_summary.user_goals if latest_summary else [],
                "decisions_made": latest_summary.decisions_made if latest_summary else [],
                "key_facts": latest_summary.key_facts if latest_summary else {},
                "constraints": latest_summary.constraints if latest_summary else {},
            } if latest_summary else {},
        }

        return context

    async def delete_session(self, session_id: str) -> None:
        """
        Delete a conversation session and all its turns.

        Args:
            session_id: Session ID
        """
        # Delete turns
        await self.db.execute(
            delete(ConversationTurn).where(ConversationTurn.session_id == session_id)
        )

        # Delete summaries
        await self.db.execute(
            delete(ConversationSummary).where(ConversationSummary.session_id == session_id)
        )

        # Delete session
        await self.db.execute(
            delete(ConversationSession).where(ConversationSession.id == session_id)
        )

        await self.db.commit()
        logger.info(f"Deleted session {session_id}")