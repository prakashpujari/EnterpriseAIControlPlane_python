#!/usr/bin/env python3
"""
Document ingestion script for Enterprise AI Customer Support Assistant.
Ingest documents from files or directories into Pinecone.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

from app.config.database import get_db_session
from app.config.settings import settings
from app.rag.ingestion import DocumentIngestor, Document
from app.rag.chunker import DocumentChunker


async def ingest_file(
    file_path: str,
    title: Optional[str] = None,
    role: str = "global",
    user_id: Optional[str] = None,
) -> dict:
    """
    Ingest a single file.

    Args:
        file_path: Path to the file
        title: Optional title
        role: Role restriction
        user_id: User ID

    Returns:
        Ingestion result
    """
    path = Path(file_path)

    if not path.exists():
        print(f"Error: File not found: {file_path}")
        return {"status": "error", "message": "File not found"}

    # Read file content
    content = path.read_text(encoding='utf-8')

    # Determine content type
    content_type = path.suffix.lstrip('.') or 'txt'

    # Create document
    document = Document(
        title=title or path.stem,
        content=content,
        content_type=content_type,
        source=f"file://{file_path}",
        role_restriction=[role] if role != "global" else ["global"],
    )

    # Ingest
    ingestor = DocumentIngestor()
    result = await ingestor.ingest_document(document, user_id)

    return {
        "status": result.status,
        "document_id": result.document_id,
        "chunks_created": result.chunks_created,
        "duration_seconds": result.duration_seconds,
    }


async def ingest_directory(
    directory: str,
    role: str = "global",
    user_id: Optional[str] = None,
) -> dict:
    """
    Ingest all documents from a directory.

    Args:
        directory: Directory path
        role: Role restriction
        user_id: User ID

    Returns:
        Summary of ingestion
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"Error: Directory not found: {directory}")
        return {"status": "error", "message": "Directory not found"}

    # Find all text files
    files = list(dir_path.glob("*.txt")) + list(dir_path.glob("*.md"))

    results = []
    for file_path in files:
        print(f"Ingesting: {file_path}")
        result = await ingest_file(str(file_path), role=role, user_id=user_id)
        results.append(result)

    return {
        "status": "success",
        "files_processed": len(results),
        "total_chunks": sum(r.get("chunks_created", 0) for r in results),
        "results": results,
    }


async def main_async(args):
    """Run ingestion."""
    if args.directory:
        result = await ingest_directory(
            args.directory,
            role=args.role,
            user_id=args.user_id,
        )
    else:
        result = await ingest_file(
            args.file,
            title=args.title,
            role=args.role,
            user_id=args.user_id,
        )

    print(f"\nResult: {result}")
    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest documents into RAG system"
    )
    parser.add_argument(
        "--file", "-f",
        help="Path to a single file to ingest",
    )
    parser.add_argument(
        "--directory", "-d",
        help="Path to directory containing documents",
    )
    parser.add_argument(
        "--title", "-t",
        help="Document title (for single file)",
    )
    parser.add_argument(
        "--role", "-r",
        default="global",
        help="Role restriction (default: global)",
    )
    parser.add_argument(
        "--user-id", "-u",
        help="User ID",
    )

    args = parser.parse_args()

    if not args.file and not args.directory:
        parser.error("Either --file or --directory is required")

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()