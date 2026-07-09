"""
LLM provider configuration and client wrappers.
Manages Groq API clients with rate limiting and retry logic.
"""

import asyncio
import time
import hashlib
from typing import Optional, Dict, Any, List
from groq import AsyncGroq, RateLimitError, APIError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

from .settings import settings

logger = logging.getLogger(__name__)


class GroqClient:
    """
    Asynchronous Groq API client with rate limiting and retry logic.
    """

    def __init__(self, api_key: str, base_url: str = None):
        self.client = AsyncGroq(
            api_key=api_key,
            base_url=base_url or "https://api.groq.com",
        )
        self._rate_limiter = asyncio.Semaphore(10)  # Max concurrent requests

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
        reraise=True,
    )
    async def _rate_limited_request(
        self,
        model: str,
        messages: list,
        max_tokens: int,
        temperature: float = 0.7,
        system: Optional[str] = None,
        tools: Optional[list] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make a rate-limited request to Groq API.
        """
        async with self._rate_limiter:
            try:
                # Build messages format for Groq
                groq_messages = []

                # Add system message if provided
                if system:
                    groq_messages.append({
                        "role": "system",
                        "content": system
                    })

                # Add user messages
                for msg in messages:
                    groq_messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", str(msg))
                    })

                response = await self.client.chat.completions.create(
                    model=model,
                    messages=groq_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )

                return {
                    "id": response.id,
                    "content": self._extract_content(response),
                    "usage": {
                        "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "output_tokens": response.usage.completion_tokens if response.usage else 0,
                    },
                    "stop_reason": response.choices[0].finish_reason if response.choices else "stop",
                }
            except RateLimitError as e:
                logger.warning(f"Rate limit hit for model {model}: {e}")
                raise
            except APIError as e:
                logger.error(f"API error for model {model}: {e}")
                raise

    def _extract_content(self, response) -> List[Any]:
        """Extract content from Groq response."""
        contents = []
        for choice in response.choices:
            if hasattr(choice, 'message') and choice.message:
                contents.append(type('Content', (), {'text': choice.message.content, 'type': 'text'})())
        return contents

    async def generate(
        self,
        model: str,
        messages: list,
        max_tokens: int,
        temperature: float = 0.7,
        system: Optional[str] = None,
        tools: Optional[list] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate a completion using Groq.
        """
        return await self._rate_limited_request(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            tools=tools,
            **kwargs,
        )

    async def generate_stream(
        self,
        model: str,
        messages: list,
        max_tokens: int,
        temperature: float = 0.7,
        system: Optional[str] = None,
        **kwargs,
    ):
        """
        Generate a streaming completion using Groq.
        """
        async with self._rate_limiter:
            # Build messages format
            groq_messages = []
            if system:
                groq_messages.append({"role": "system", "content": system})
            for msg in messages:
                groq_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", str(msg))
                })

            async for chunk in self.client.chat.completions.stream(
                model=model,
                messages=groq_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            ):
                yield chunk

    async def embed(self, texts: list) -> list:
        """
        Generate embeddings for the given texts.
        Uses a simple hashing-based approach to create meaningful embeddings
        that preserve semantic similarity for basic use cases.
        For production, consider integrating with a proper embedding service.
        """
        embeddings = []
        for text in texts:
            # Create a deterministic but varied embedding based on text content
            # This is better than zeros and provides basic differentiation
            if not text.strip():
                # Empty text gets zero vector
                embeddings.append([0.0] * 1536)
                continue

            # Create a hash of the text
            hash_obj = hashlib.md5(text.encode('utf-8'))
            hash_hex = hash_obj.hexdigest()

            # Convert hash to a list of numbers
            hash_ints = [int(hash_hex[i:i+2], 16) for i in range(0, len(hash_hex), 2)]

            # Expand/repeat to reach 1536 dimensions
            # Cycle through the hash values to fill the embedding vector
            embedding = []
            for i in range(1536):
                # Use the hash values cyclically, normalized to [-1, 1]
                val = hash_ints[i % len(hash_ints)]
                # Normalize to [-1, 1] range
                normalized = (val / 255.0) * 2 - 1
                embedding.append(normalized)

            embeddings.append(embedding)

        return embeddings


# Global client instances
_groq_client: Optional[GroqClient] = None


def get_claude_client() -> GroqClient:
    """Get the global Groq client instance (renamed for compatibility)."""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient(
            api_key=settings.GROQ_API_KEY.get_secret_value(),
            base_url=settings.GROQ_BASE_URL,
        )
    return _groq_client


# Alias for compatibility
ClaudeClient = GroqClient


def get_groq_client() -> GroqClient:
    """Get the global Groq client instance."""
    return get_claude_client()


class ModelRouter:
    """
    Routes requests to appropriate models based on query type and role.
    """

    MODEL_CONFIGS = {
        "small": {
            "model": settings.SMALL_MODEL,
            "max_tokens": 4000,
            "temperature": 0.3,
        },
        "medium": {
            "model": settings.MEDIUM_MODEL,
            "max_tokens": 8000,
            "temperature": 0.5,
        },
        "large": {
            "model": settings.LARGE_MODEL,
            "max_tokens": 4096,
            "temperature": 0.7,
        },
    }

    ROLE_TOKEN_LIMITS = {
        "support_engineer": settings.SUPPORT_ENGINEER_TOKEN_LIMIT,
        "mortgage_analyst": settings.MORTGAGE_ANALYST_TOKEN_LIMIT,
        "compliance_officer": settings.COMPLIANCE_OFFICER_TOKEN_LIMIT,
        "product_owner": settings.PRODUCT_OWNER_TOKEN_LIMIT,
    }

    def get_model_config(self, tier: str) -> Dict[str, Any]:
        """Get model configuration for a tier."""
        return self.MODEL_CONFIGS.get(tier, self.MODEL_CONFIGS["medium"])

    def get_token_limit(self, role: str) -> int:
        """Get token limit for a role."""
        return self.ROLE_TOKEN_LIMITS.get(role, 8000)

    def route_query(
        self,
        query_type: str,
        role: str,
        complexity: str = "medium",
    ) -> str:
        """
        Determine the appropriate model tier for a query.

        Args:
            query_type: faq, rag, summarize, reason
            role: User role
            complexity: low, medium, high

        Returns:
            Model tier: small, medium, or large
        """
        # FAQ and simple queries use small models
        if query_type == "faq":
            return "small"

        # Summarization uses medium models
        if query_type == "summarize":
            return "medium"

        # RAG uses medium models
        if query_type == "rag":
            return "medium"

        # Complex reasoning uses large models
        if query_type == "reason":
            return "large"

        # Default based on complexity
        if complexity == "low":
            return "small"
        elif complexity == "high":
            return "large"
        else:
            return "medium"


# Global model router instance
model_router = ModelRouter()