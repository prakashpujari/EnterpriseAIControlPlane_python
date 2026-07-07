"""
Rate limiting module for FastAPI Gateway.
Implements Redis-backed rate limiting with per-role, per-endpoint limits.
"""

import time
from typing import Optional, Callable, Dict, Any
from functools import wraps
import asyncio
import logging

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config.settings import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Redis-backed rate limiter.
    """

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Rate limit key (e.g., "user:123:endpoint:chat")
            limit: Maximum requests allowed in window
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        redis_key = f"rate_limit:{key}"

        try:
            # Use Redis pipeline for atomic operation
            async with self.client.pipeline() as pipe:
                pipe.incr(redis_key)
                pipe.ttl(redis_key)
                results = await pipe.execute()

            current = results[0]
            ttl = results[1]

            if ttl == -1:
                # Key doesn't exist, set expiration
                await self.client.expire(redis_key, window)
                ttl = window

            remaining = max(0, limit - current)
            is_allowed = current <= limit

            return is_allowed, remaining, ttl

        except Exception as e:
            logger.error(f"Rate limit error: {e}")
            # Fail open - allow request if Redis is down
            return True, limit, window

    async def check_user_rate_limit(
        self,
        user_id: str,
        endpoint: str = "general",
    ) -> tuple[bool, int, int]:
        """
        Check user-specific rate limit.

        Args:
            user_id: User ID
            endpoint: Endpoint name

        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        key = f"user:{user_id}:endpoint:{endpoint}"
        return await self.is_allowed(
            key,
            settings.REQUESTS_PER_MINUTE_PER_USER,
            60,  # 1 minute window
        )

    async def check_role_rate_limit(
        self,
        role: str,
        endpoint: str = "general",
    ) -> tuple[bool, int, int]:
        """
        Check role-based rate limit.

        Args:
            role: User role
            endpoint: Endpoint name

        Returns:
            Tuple of (is_allowed, remaining, reset_time)
        """
        key = f"role:{role}:endpoint:{endpoint}"
        return await self.is_allowed(
            key,
            settings.REQUESTS_PER_MINUTE_PER_USER * 2,  # Higher limit for role
            60,
        )


class RateLimitExceeded(HTTPException):
    """Exception for rate limit exceeded."""

    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
        )


def rate_limit(
    key_func: Callable[[Request], str] = None,
    limit: int = None,
    window: int = 60,
):
    """
    Decorator for rate limiting FastAPI endpoints.

    Args:
        key_func: Function to extract rate limit key from request
        limit: Maximum requests allowed (default from settings)
        window: Time window in seconds

    Returns:
        Decorator function
    """
    limiter = RateLimiter()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This is a simplified version - real implementation would use
            # FastAPI dependencies for proper injection
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# FastAPI dependency for rate limiting
async def check_rate_limit(
    request: Request,
    user_id: Optional[str] = None,
    role: Optional[str] = None,
) -> None:
    """
    FastAPI dependency to check rate limits.

    Args:
        request: FastAPI request object
        user_id: User ID from auth
        role: User role from auth

    Raises:
        HTTPException: If rate limit exceeded
    """
    if user_id is None:
        return  # Allow unauthenticated requests (handled by auth)

    limiter = RateLimiter()

    # Check user rate limit
    is_allowed, remaining, reset_time = await limiter.check_user_rate_limit(
        user_id,
        request.url.path,
    )

    if not is_allowed:
        logger.warning(f"Rate limit exceeded for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in {reset_time} seconds.",
            headers={
                "X-RateLimit-Limit": str(settings.REQUESTS_PER_MINUTE_PER_USER),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(int(time.time()) + reset_time),
            },
        )


# Token bucket implementation for more sophisticated rate limiting
class TokenBucket:
    """
    Token bucket rate limiting algorithm.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum tokens
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens: Dict[str, float] = {}
        self.last_refill: Dict[str, float] = {}

    def _refill(self, key: str) -> None:
        """Refill tokens based on time elapsed."""
        now = time.time()
        if key not in self.last_refill:
            self.last_refill[key] = now
            self.tokens[key] = self.capacity

        elapsed = now - self.last_refill[key]
        self.tokens[key] = min(
            self.capacity,
            self.tokens[key] + elapsed * self.refill_rate,
        )
        self.last_refill[key] = now

    def consume(self, key: str, tokens: float = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            key: Unique key for bucket
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limited
        """
        self._refill(key)

        if self.tokens[key] >= tokens:
            self.tokens[key] -= tokens
            return True
        return False


# Global rate limiter instance
rate_limiter = RateLimiter()