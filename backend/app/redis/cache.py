"""
Conversation list cache using Redis.

Key:  convs:{user_id}
TTL:  60 seconds

The cache stores the full serialised JSON of the conversation list response.
It is invalidated whenever a new message is sent to any conversation the
user belongs to.
"""

import json
import logging
from typing import Any, Optional

from app.redis.client import get_redis

logger = logging.getLogger(__name__)

_TTL = 60  # seconds


def _key(user_id: str) -> str:
    return f"convs:{user_id}"


async def get_conversations_cache(user_id: str) -> Optional[list]:
    """Return cached conversation list or None on cache miss."""
    r = await get_redis()
    raw = await r.get(_key(user_id))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Corrupt conversation cache for user %s — ignoring", user_id)
        return None


async def set_conversations_cache(user_id: str, data: Any) -> None:
    """Serialise and cache the conversation list for 60 seconds."""
    r = await get_redis()
    payload = json.dumps(data, default=str)
    await r.set(_key(user_id), payload, ex=_TTL)


async def invalidate_conversations_cache(user_id: str) -> None:
    """Delete the cached conversation list for a user."""
    r = await get_redis()
    await r.delete(_key(user_id))


async def invalidate_many(user_ids: list[str]) -> None:
    """Batch-delete conversation cache for multiple users."""
    if not user_ids:
        return
    r = await get_redis()
    keys = [_key(uid) for uid in user_ids]
    await r.delete(*keys)
