"""
Documents API router for RAG document management.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import io
import PyPDF2

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.config.database import get_db_session
from app.models.database import User
from app.gateway.auth import get_current_active_user
from app.rag.ingestion import Document, DocumentIngestor, get_ingestor
from app.rag.retriever import RAGEngine, get_rag_engine

router = APIRouter()
logger = logging.getLogger(__name__)


class DocumentCreate(BaseModel):
    """Request model for creating a document."""

    title: str
    content: str
    content_type: str = "text"
    source: str = "user_upload"
    role_restriction: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentResponse(BaseModel):
    """Response model for documents."""

    id: str
    title: str
    content_type: str
    source: str
    created_at: datetime
    is_active: bool


@router.post("/documents", response_model=DocumentResponse)
async def create_document(
    document: DocumentCreate,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    Create and index a document for RAG.

    Args:
        document: Document data
        db_session: Database session
        user: Authenticated user

    Returns:
        Created document info
    """
    ingestor = get_ingestor(db_session)

    doc = Document(
        title=document.title,
        content=document.content,
        content_type=document.content_type,
        source=document.source,
        role_restriction=document.role_restriction or ["global"],
        metadata=document.metadata,
    )

    result = await ingestor.ingest_document(doc, user_id=user.id)

    return DocumentResponse(
        id=result.document_id,
        title=document.title,
        content_type=document.content_type,
        source=document.source,
        created_at=datetime.utcnow(),
        is_active=result.status == "success",
    )


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    List documents.

    Args:
        skip: Number of records to skip
        limit: Maximum records to return
        db_session: Database session
        user: Authenticated user

    Returns:
        List of documents
    """
    result = await db_session.execute(
        text("SELECT id, title, content_type, source_url AS source, created_at, is_active FROM documents ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
        {"limit": limit, "skip": skip},
    )

    documents = []
    for row in result:
        documents.append(DocumentResponse(
            id=row.id,
            title=row.title,
            content_type=row.content_type,
            source=row.source,
            created_at=row.created_at,
            is_active=row.is_active,
        ))

    return documents


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    Get a specific document.

    Args:
        document_id: Document ID
        db_session: Database session
        user: Authenticated user

    Returns:
        Document info
    """
    result = await db_session.execute(
        text("SELECT id, title, content_type, source_url AS source, created_at, is_active FROM documents WHERE id = :id"),
        {"id": document_id},
    )

    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=row.id,
        title=row.title,
        content_type=row.content_type,
        source=row.source,
        created_at=row.created_at,
        is_active=row.is_active,
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    Delete a document.

    Args:
        document_id: Document ID
        db_session: Database session
        user: Authenticated user

    Returns:
        Success message
    """
    ingestor = get_ingestor(db_session)
    success = await ingestor.delete_document(document_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete document")

    return {"message": "Document deleted successfully"}


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = None,
    db_session: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
):
    """
    Upload a document file.

    Args:
        file: Uploaded file
        title: Optional title
        db_session: Database session
        user: Authenticated user

    Returns:
        Upload result
    """
    content = await file.read()

    # Determine content type
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "uploaded_document"

    # Extract text based on file type
    extracted_text = ""
    if content_type == "application/pdf" or filename.lower().endswith('.pdf'):
        # Extract text from PDF
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_pages = []
            for page in pdf_reader.pages:
                text_page = page.extract_text()
                if text_page:  # Only add non-empty text
                    text_pages.append(text_page)
            extracted_text = "\n".join(text_pages)
            # Check if we got meaningful text
            if not extracted_text.strip():
                raise ValueError("PDF text extraction resulted in empty content")
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract text from PDF: {str(e)}. Please ensure the PDF contains extractable text or try a different format."
            )
    else:
        # For other file types, decode as UTF-8 text
        try:
            extracted_text = content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to decode file content: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to decode file content: {str(e)}"
            )

    # Create document
    doc = Document(
        title=title or filename or "Uploaded Document",
        content=extracted_text,
        content_type=content_type,
        source=f"upload:{filename}",
    )

    ingestor = get_ingestor(db_session)
    result = await ingestor.ingest_document(doc, user_id=user.id)

    return {
        "document_id": result.document_id,
        "chunks_created": result.chunks_created,
        "status": result.status,
    }