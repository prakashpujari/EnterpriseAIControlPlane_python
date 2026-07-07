"""
Document chunking module for RAG.
Implements recursive chunking with metadata extraction.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A document chunk."""

    content: str
    chunk_index: int
    start_char: int
    end_char: int
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DocumentChunker:
    """
    Recursive document chunker for RAG.
    Splits documents into manageable chunks with metadata.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separator: str = "\n\n",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator

    def chunk_document(
        self,
        content: str,
        title: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Chunk]:
        """
        Chunk a document into smaller pieces.

        Args:
            content: Document content
            title: Document title
            source: Document source
            metadata: Additional metadata

        Returns:
            List of chunks
        """
        if not content:
            return []

        # Clean content
        content = self._clean_content(content)

        # Split into chunks
        chunks = self._split_recursive(content)

        # Add metadata
        for i, chunk in enumerate(chunks):
            chunk.title = title
            chunk.metadata = {
                "source": source,
                "chunk_index": i,
                "token_count": len(chunk.content.split()),
                "content_type": metadata.get("content_type", "text") if metadata else "text",
                **(metadata or {}),
            }

        return chunks

    def _clean_content(self, content: str) -> str:
        """
        Clean document content.

        Args:
            content: Raw content

        Returns:
            Cleaned content
        """
        # Remove excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r'[ \t]{2,}', ' ', content)

        # Remove HTML tags if present
        content = re.sub(r'<[^>]+>', '', content)

        # Trim
        content = content.strip()

        return content

    def _split_recursive(self, content: str) -> List[Chunk]:
        """
        Recursively split content into chunks.

        Args:
            content: Content to split

        Returns:
            List of chunks
        """
        chunks = []
        current_pos = 0
        chunk_index = 0

        while current_pos < len(content):
            # Find chunk end
            end_pos = current_pos + self.chunk_size

            if end_pos >= len(content):
                # Last chunk
                chunk_content = content[current_pos:]
            else:
                # Look for separator
                separator_pos = content.rfind(
                    self.separator,
                    current_pos,
                    end_pos + self.chunk_overlap
                )

                if separator_pos > current_pos:
                    end_pos = separator_pos + len(self.separator)
                else:
                    # No separator found, split at chunk_size
                    end_pos = min(current_pos + self.chunk_size, len(content))

            chunk_content = content[current_pos:end_pos]

            if chunk_content.strip():
                chunks.append(Chunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                    start_char=current_pos,
                    end_char=end_pos,
                ))
                chunk_index += 1

            # Move position with overlap
            current_pos = end_pos - self.chunk_overlap if end_pos > self.chunk_overlap else end_pos

        return chunks


class MetadataExtractor:
    """
    Extracts metadata from documents.
    """

    @staticmethod
    def extract_title(content: str, default: str = "Untitled") -> str:
        """
        Extract title from content.

        Args:
            content: Document content
            default: Default title

        Returns:
            Extracted or default title
        """
        # Try to find title in first few lines
        lines = content.split('\n')[:5]

        for line in lines:
            line = line.strip()
            if line and len(line) < 100:
                # Check if it looks like a title (not a heading with #, not too long)
                if not line.startswith('#') and not re.match(r'^\d+\.', line):
                    return line

        return default

    @staticmethod
    def extract_content_type(content: str) -> str:
        """
        Detect content type.

        Args:
            content: Document content

        Returns:
            Content type string
        """
        if content.strip().startswith('<'):
            return "html"
        elif re.search(r'\*\s*', content[:500]):  # Markdown
            return "markdown"
        else:
            return "text"

    @staticmethod
    def extract_role_tags(content: str) -> List[str]:
        """
        Extract role tags from content.

        Args:
            content: Document content

        Returns:
            List of roles the content is relevant to
        """
        # Look for role indicators in content
        roles = []

        role_patterns = {
            "support_engineer": ["ticket", "customer", "account", "refund", "billing", "support"],
            "mortgage_analyst": ["mortgage", "loan", "rate", "apr", "underwriting", "appraisal"],
            "compliance_officer": ["compliance", "audit", "regulation", "policy", "review", "ocpa"],
            "product_owner": ["feature", "product", "release", "roadmap", "user story", "requirement"],
        }

        content_lower = content.lower()

        for role, keywords in role_patterns.items():
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches >= 2:  # Require at least 2 keyword matches
                roles.append(role)

        return roles if roles else ["global"]


# Global chunker instance
chunker = DocumentChunker()


def get_chunker(
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> DocumentChunker:
    """
    Get a document chunker instance.

    Args:
        chunk_size: Maximum chunk size in characters
        chunk_overlap: Overlap between chunks

    Returns:
        DocumentChunker instance
    """
    return DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)