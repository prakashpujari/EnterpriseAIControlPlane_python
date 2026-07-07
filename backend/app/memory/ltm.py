"""
Long-term Memory (LTM) implementation.
Stores facts, preferences, and decisions in Pinecone for semantic retrieval.
"""

import uuid
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import logging

from pinecone import Pinecone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.config.pinecone_client import get_ltm_index, NAMESPACES
from app.config.llm_providers import get_claude_client, model_router

logger = logging.getLogger(__name__)


class LTMManager:
    """
    Long-term Memory Manager.
    Stores and retrieves semantic facts using Pinecone vector database.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
        self.client = get_claude_client()
        self.index = get_ltm_index()

    async def store_fact(
        self,
        user_id: str,
        fact_key: str,
        fact_value: str,
        namespace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a fact in long-term memory.

        Args:
            user_id: User ID
            fact_key: Fact identifier/key
            fact_value: Fact value/content
            namespace: Optional namespace override
            metadata: Additional metadata

        Returns:
            Vector ID
        """
        # Generate embedding
        embedding = await self._get_embedding(fact_value)

        # Use default namespace if not provided
        if namespace is None:
            namespace = NAMESPACES["ltm"]["facts"]

        vector_id = f"{user_id}:{fact_key}:{int(time.time())}"

        # Prepare metadata
        fact_metadata = {
            "user_id": user_id,
            "fact_key": fact_key,
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }

        # Upsert to Pinecone
        await self.index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": fact_metadata,
                }
            ],
            namespace=namespace,
        )

        logger.info(f"Stored fact '{fact_key}' for user {user_id}")
        return vector_id

    async def store_preference(
        self,
        user_id: str,
        preference_key: str,
        preference_value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a user preference.

        Args:
            user_id: User ID
            preference_key: Preference identifier
            preference_value: Preference value
            metadata: Additional metadata

        Returns:
            Vector ID
        """
        # Convert value to string for embedding
        value_str = str(preference_value)

        # Generate embedding
        embedding = await self._get_embedding(value_str)

        namespace = NAMESPACES["ltm"]["preferences"]
        vector_id = f"{user_id}:pref:{preference_key}:{int(time.time())}"

        # Prepare metadata
        pref_metadata = {
            "user_id": user_id,
            "preference_key": preference_key,
            "preference_value": value_str,
            "type": type(preference_value).__name__,
            "created_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }

        # Upsert to Pinecone
        await self.index.upsert(
            vectors=[
                {
                    "id": vector_id,
                    "values": embedding,
                    "metadata": pref_metadata,
                }
            ],
            namespace=namespace,
        )

        logger.info(f"Stored preference '{preference_key}' for user {user_id}")
        return vector_id

    async def retrieve_facts(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant facts for a query.

        Args:
            user_id: User ID
            query: Query string
            top_k: Number of results to retrieve
            include_metadata: Whether to include metadata

        Returns:
            List of matching facts with scores
        """
        # Generate query embedding
        query_embedding = await self._get_embedding(query)

        # Search in facts namespace
        namespace = NAMESPACES["ltm"]["facts"]

        results = await self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=include_metadata,
            filter={"user_id": user_id} if user_id else None,
        )

        # Format results
        facts = []
        for match in results.matches:
            fact = {
                "id": match.id,
                "score": match.score,
                "fact_key": match.metadata.get("fact_key", ""),
                "fact_value": match.metadata.get("fact_value", match.metadata.get("fact_key", "")),
                "created_at": match.metadata.get("created_at"),
            }
            facts.append(fact)

        logger.debug(f"Retrieved {len(facts)} facts for query '{query}'")
        return facts

    async def retrieve_preferences(
        self,
        user_id: str,
        query: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve user preferences.

        Args:
            user_id: User ID
            query: Optional query string
            top_k: Number of results

        Returns:
            List of preferences
        """
        if query:
            query_embedding = await self._get_embedding(query)
        else:
            # Use zero vector for preference retrieval by user only
            query_embedding = [0.0] * 1536

        namespace = NAMESPACES["ltm"]["preferences"]

        results = await self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
            filter={"user_id": user_id},
        )

        preferences = []
        for match in results.matches:
            pref = {
                "id": match.id,
                "score": match.score,
                "key": match.metadata.get("preference_key", ""),
                "value": match.metadata.get("preference_value", ""),
                "type": match.metadata.get("type", "string"),
            }
            preferences.append(pref)

        return preferences

    async def search_conversations(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant past conversations.

        Args:
            user_id: User ID
            query: Search query
            top_k: Number of results

        Returns:
            List of matching conversations
        """
        query_embedding = await self._get_embedding(query)

        namespace = NAMESPACES["ltm"]["conversations"]

        results = await self.index.query(
            vector=query_embedding,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True,
            filter={"user_id": user_id},
        )

        conversations = []
        for match in results.matches:
            conv = {
                "id": match.id,
                "score": match.score,
                "session_id": match.metadata.get("session_id", ""),
                "created_at": match.metadata.get("created_at"),
            }
            conversations.append(conv)

        return conversations

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for text using Claude.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Clean text
        text = text.strip()[:8000]  # Claude has token limits

        embeddings = await self.client.embed(text)
        return embeddings[0]

    async def delete_user_facts(self, user_id: str) -> int:
        """
        Delete all facts for a user (e.g., on account deletion).

        Args:
            user_id: User ID

        Returns:
            Number of deleted vectors
        """
        # Pinecone doesn't support delete by filter directly
        # We need to query first, then delete
        results = await self.index.query(
            vector=[0.0] * 1536,  # Dummy query
            top_k=10000,
            namespace=NAMESPACES["ltm"]["facts"],
            filter={"user_id": user_id},
        )

        if results.matches:
            ids_to_delete = [m.id for m in results.matches]
            await self.index.delete(ids=ids_to_delete, namespace=NAMESPACES["ltm"]["facts"])
            logger.info(f"Deleted {len(ids_to_delete)} facts for user {user_id}")
            return len(ids_to_delete)

        return 0

    async def get_user_profile(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get user profile from stored facts and preferences.

        Args:
            user_id: User ID

        Returns:
            User profile dict
        """
        # Get preferences
        preferences = await self.retrieve_preferences(user_id)

        # Get key facts
        facts = await self.retrieve_facts(user_id, "user profile customer", top_k=10)

        profile = {
            "preferences": {p["key"]: p["value"] for p in preferences},
            "facts": {f["fact_key"]: f["fact_value"] for f in facts},
        }

        return profile


# Global LTM manager instance
ltm_manager: Optional[LTMManager] = None


def get_ltm_manager(db_session: Optional[AsyncSession] = None) -> LTMManager:
    """Get or create the global LTM manager instance."""
    global ltm_manager
    if ltm_manager is None:
        ltm_manager = LTMManager(db_session)
    return ltm_manager