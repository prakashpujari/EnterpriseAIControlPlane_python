"""
Test configuration and fixtures for Enterprise AI Control Plane tests.
"""
import pytest
from app.config.pinecone_client import pc, USE_MOCK_PINECONE
from app.rag.ingestion import DocumentIngestor


@pytest.fixture(autouse=True)
def reset_mock_pinecone():
    """Reset mock Pinecone state between tests."""
    if USE_MOCK_PINECONE and hasattr(pc, '_indexes'):
        pc._indexes.clear()
    yield
    if USE_MOCK_PINECONE and hasattr(pc, '_indexes'):
        pc._indexes.clear()


@pytest.fixture(autouse=True)
def reset_global_instances():
    """Reset global singleton instances between tests."""
    # Reset RAG engine
    import app.rag.retriever as retriever_module
    retriever_module.rag_engine = None

    # Reset chat workflow
    import app.orchestration.workflow as workflow_module
    workflow_module.chat_workflow = None

    # Reset ingestor
    import app.rag.ingestion as ingestion_module
    ingestion_module.ingestor = DocumentIngestor()

    yield

    # Cleanup after test
    retriever_module.rag_engine = None
    workflow_module.chat_workflow = None
    ingestion_module.ingestor = DocumentIngestor()