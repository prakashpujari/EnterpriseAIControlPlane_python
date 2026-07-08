"""
Document ingestion pipeline for RAG.
Handles document processing, embedding, and indexing.
"""

import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.config.pinecone_client import get_rag_index, NAMESPACES
from app.config.llm_providers import get_claude_client
from app.memory.ltm import LTMManager
from .chunker import DocumentChunker, MetadataExtractor
from app.models.database import Document as DBDocument  # SQLAlchemy model

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Document to be ingested (input to the ingestion pipeline)."""

    title: str
    content: str
    content_type: str = "text"
    source: str = "user_upload"
    s3_key: Optional[str] = None
    role_restriction: List[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class IngestionResult:
    """Result of document ingestion."""

    document_id: str
    chunks_created: int
    vectors_indexed: int
    duration_seconds: float
    status: str


class DocumentIngestor:
    """
    Handles document ingestion into RAG system.
    Processes documents, creates embeddings, and indexes in Pinecone.
    """

    def __init__(self, db_session: Optional[AsyncSession] = None):
        self.db = db_session
        self.client = get_claude_client()
        self.chunker = DocumentChunker(
            chunk_size=settings.RAG_TOP_K * 200,  # ~200 chars per token
            chunk_overlap=100,
        )
        self.ltm_manager = LTMManager(db_session)

    async def ingest_document(
        self,
        document: Document,
        user_id: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest a document into the RAG system.

        Args:
            document: Document to ingest
            user_id: User ID who uploaded the document

        Returns:
            IngestionResult with details
        """
        start_time = datetime.utcnow()

        try:
            # Create document record
            document_id = await self._create_document_record(document, user_id)

            # Chunk document
            chunks = self.chunker.chunk_document(
                content=document.content,
                title=document.title,
                source=document.source,
                metadata={
                    "content_type": document.content_type,
                    "s3_key": document.s3_key,
                    "role_restriction": document.role_restriction or ["global"],
                    **(document.metadata or {}),
                },
            )

            # Create embeddings and index
            vectors_created = await self._index_chunks(document_id, chunks)

            duration = (datetime.utcnow() - start_time).total_seconds()

            result = IngestionResult(
                document_id=document_id,
                chunks_created=len(chunks),
                vectors_indexed=vectors_created,
                duration_seconds=duration,
                status="success",
            )

            logger.info(f"Ingested document '{document.title}': {len(chunks)} chunks")

            return result

        except Exception as e:
            logger.error(f"Failed to ingest document: {e}")
            return IngestionResult(
                document_id="",
                chunks_created=0,
                vectors_indexed=0,
                duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                status=f"error: {str(e)}",
            )

    async def _create_document_record(
        self,
        document: Document,
        user_id: Optional[str],
    ) -> str:
        """
        Create document record in database.

        Args:
            document: Document object
            user_id: User ID

        Returns:
            Document ID
        """
        if self.db is None:
            return str(uuid.uuid4())

        document_id = str(uuid.uuid4())

        stmt = insert(DBDocument).values(
            id=document_id,
            title=document.title,
            content=document.content[:10000] if len(document.content) > 10000 else document.content,
            content_type=document.content_type,
            source_url=document.source,
            s3_key=document.s3_key,
            namespace=NAMESPACES["rag"]["global"],
            role_restriction=document.role_restriction or ["global"],
            doc_metadata=document.metadata,
            is_active=True,
            created_by=user_id,
            created_at=datetime.utcnow(),
            indexed_at=datetime.utcnow(),
        )

        await self.db.execute(stmt)
        await self.db.commit()

        return document_id

    async def _index_chunks(
        self,
        document_id: str,
        chunks: List[Any],
    ) -> int:
        """
        Index document chunks in Pinecone.

        Args:
            document_id: Document ID
            chunks: List of Chunk objects

        Returns:
            Number of vectors indexed
        """
        index = get_rag_index()

        # Create embeddings for all chunks
        embeddings = await self._create_embeddings([c.content for c in chunks])

        # Prepare vectors for upsert
        vectors = []
        namespace = NAMESPACES["rag"]["global"]

        for i, chunk in enumerate(chunks):
            vector = {
                "id": f"{document_id}_chunk_{i}",
                "values": embeddings[i],
                "metadata": {
                    "document_id": document_id,
                    "chunk_index": i,
                    "title": chunk.title or "Document",
                    "content": chunk.content[:1000],  # Trim for metadata
                    "source": chunk.metadata.get("source", "Unknown"),
                    "role_restriction": chunk.metadata.get("role_restriction", ["global"]),
                    "content_type": chunk.metadata.get("content_type", "text"),
                },
            }
            vectors.append(vector)

        # Upsert to Pinecone
        await index.upsert(vectors=vectors, namespace=namespace)

        return len(vectors)

    async def _create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Create embeddings for texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings
        """
        # Process in batches
        batch_size = 32
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await self.client.embed(batch)
            extend = list.extend
            extend(embeddings, batch_embeddings)

        return embeddings

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its chunks.

        Args:
            document_id: Document ID

        Returns:
            True if deleted successfully
        """
        try:
            # Delete from Pinecone
            index = get_rag_index()
            await index.delete(
                ids=[f"{document_id}_chunk_{i}" for i in range(1000)],  # Approximate max chunks
                namespace=NAMESPACES["rag"]["global"],
            )

            # Delete from database
            if self.db:
                await self.db.execute(
                    text("DELETE FROM document_chunks WHERE document_id = :id"),
                    {"id": document_id},
                )
                await self.db.execute(
                    text("DELETE FROM documents WHERE id = :id"),
                    {"id": document_id},
                )
                await self.db.commit()

            logger.info(f"Deleted document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False


# Global ingestor instance
ingestor = DocumentIngestor()


def get_ingestor(db_session: Optional[AsyncSession] = None) -> DocumentIngestor:
    """Get or create the global document ingestor instance."""
    global ingestor
    if ingestor.db is None and db_session:
        ingestor.db = db_session
    return ingestor