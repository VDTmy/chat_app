"""
Async Redis client singleton using redis.asyncio.

Usage:
    from app.redis.client import get_redis
    redis = await get_redis()
"""

import logging
from typing import Optional

# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client initialised — %s", settings.REDIS_URL)
    return _redis_client


async def close_redis() -> None:
    """Close the shared Redis connection (call on app shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis client closed")
