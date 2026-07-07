"""
Pinecone vector database client configuration.
Manages RAG and LTM index connections.
"""

import os
from typing import Optional, List, Dict, Any
import logging

from .settings import settings

logger = logging.getLogger(__name__)


class MockPineconeIndex:
    """Mock Pinecone index for testing."""

    def __init__(self, name: str):
        self.name = name
        self._vectors: Dict[str, Dict[str, Any]] = {}

    async def upsert(self, vectors: List[Dict[str, Any]], namespace: str = "") -> None:
        """Mock upsert."""
        for vec in vectors:
            self._vectors[vec["id"]] = vec
        logger.debug(f"Mock upsert: {len(vectors)} vectors to {self.name}/{namespace}")

    async def query(
        self,
        vector: List[float],
        top_k: int = 5,
        namespace: str = "",
        include_metadata: bool = True,
        filter: Optional[Dict[str, Any]] = None,
    ):
        """Mock query - returns empty results."""
        from types import SimpleNamespace

        class MockMatch:
            def __init__(self, id: str, score: float, metadata: Dict[str, Any]):
                self.id = id
                self.score = score
                self.metadata = metadata

        class MockResult:
            def __init__(self, matches: List[MockMatch]):
                self.matches = matches

        return MockResult([])

    async def delete(self, ids: List[str], namespace: str = "") -> None:
        """Mock delete."""
        for id in ids:
            self._vectors.pop(id, None)
        logger.debug(f"Mock delete: {len(ids)} vectors from {self.name}/{namespace}")


class MockPinecone:
    """Mock Pinecone client for testing."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._indexes: Dict[str, MockPineconeIndex] = {}

    def list_indexes(self) -> List:
        """List mock indexes."""
        from types import SimpleNamespace
        return [SimpleNamespace(name=name) for name in self._indexes.keys()]

    def create_index(self, name: str, dimension: int, metric: str, spec: Any) -> None:
        """Create mock index."""
        self._indexes[name] = MockPineconeIndex(name)
        logger.info(f"Created mock index: {name}")

    def Index(self, name: str, host: Optional[str] = None, pool_threads: int = 1):
        """Get mock index."""
        if name not in self._indexes:
            self._indexes[name] = MockPineconeIndex(name)
        return self._indexes[name]


# Check if using mock Pinecone
api_key_value = settings.PINECONE_API_KEY.get_secret_value()
USE_MOCK_PINECONE = api_key_value == "mock_pinecone_key"
logger.info(f"PINECONE_API_KEY value: {api_key_value}")
logger.info(f"USE_MOCK_PINECONE: {USE_MOCK_PINECONE}")

# Initialize Pinecone client
if USE_MOCK_PINECONE:
    pc = MockPinecone(settings.PINECONE_API_KEY.get_secret_value())
    logger.info("Using mock Pinecone client for testing")
else:
    from pinecone import Pinecone, ServerlessSpec
    pc = Pinecone(
        api_key=settings.PINECONE_API_KEY.get_secret_value(),
    )


def get_rag_index_name() -> str:
    """Get the RAG index name."""
    return settings.PINECONE_RAG_INDEX


def get_ltm_index_name() -> str:
    """Get the LTM index name."""
    return settings.PINECONE_LTM_INDEX


async def init_pinecone_indexes() -> None:
    """
    Initialize Pinecone indexes if they don't exist.
    Creates RAG and LTM indexes with appropriate dimensions.
    """
    if USE_MOCK_PINECONE:
        # For mock, just ensure indexes exist
        if settings.PINECONE_RAG_INDEX not in [idx.name for idx in pc.list_indexes()]:
            pc.create_index(
                name=settings.PINECONE_RAG_INDEX,
                dimension=1536,
                metric="cosine",
                spec=None,
            )
        if settings.PINECONE_LTM_INDEX not in [idx.name for idx in pc.list_indexes()]:
            pc.create_index(
                name=settings.PINECONE_LTM_INDEX,
                dimension=1536,
                metric="cosine",
                spec=None,
            )
        logger.info("Mock Pinecone indexes initialized")
        return

    # Real Pinecone initialization
    # Claude embeddings are 1536 dimensions
    dimension = 1536
    metric = "cosine"

    # Get existing indexes
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    # RAG Index
    if settings.PINECONE_RAG_INDEX not in existing_indexes:
        logger.info(f"Creating RAG index: {settings.PINECONE_RAG_INDEX}")
        pc.create_index(
            name=settings.PINECONE_RAG_INDEX,
            dimension=dimension,
            metric=metric,
            spec=ServerlessSpec(
                cloud="aws",
                region=settings.PINECONE_ENVIRONMENT,
            ),
        )

    # LTM Index
    if settings.PINECONE_LTM_INDEX not in existing_indexes:
        logger.info(f"Creating LTM index: {settings.PINECONE_LTM_INDEX}")
        pc.create_index(
            name=settings.PINECONE_LTM_INDEX,
            dimension=dimension,
            metric=metric,
            spec=ServerlessSpec(
                cloud="aws",
                region=settings.PINECONE_ENVIRONMENT,
            ),
        )


def get_rag_index():
    """Get the RAG index client (lazy initialization)."""
    return pc.Index(settings.PINECONE_RAG_INDEX)


def get_ltm_index():
    """Get the LTM index client (lazy initialization)."""
    return pc.Index(settings.PINECONE_LTM_INDEX)


# Namespace constants
NAMESPACES = {
    "rag": {
        "support_engineer": "role:support_engineer",
        "mortgage_analyst": "role:mortgage_analyst",
        "compliance_officer": "role:compliance_officer",
        "product_owner": "role:product_owner",
        "global": "role:global",
    },
    "ltm": {
        "preferences": "user:preferences",
        "facts": "facts:decisions",
        "conversations": "conversations:extracted",
    },
}


def get_namespace(doc_type: str, role: Optional[str] = None) -> str:
    """
    Get the appropriate namespace for a document or query.

    Args:
        doc_type: 'rag' or 'ltm'
        role: User role (for RAG) or user_id (for LTM)

    Returns:
        Namespace string
    """
    if doc_type == "rag":
        if role and role in NAMESPACES["rag"]:
            return NAMESPACES["rag"][role]
        return NAMESPACES["rag"]["global"]
    elif doc_type == "ltm":
        if role:
            return f"{NAMESPACES['ltm']['facts']}:{role}"
        return NAMESPACES["ltm"]["facts"]
    else:
        raise ValueError(f"Unknown doc_type: {doc_type}")