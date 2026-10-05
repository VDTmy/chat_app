"""
Typing indicator management via Redis.

Keys:
    typing:{conversation_id}:{user_id}  → "1"  EX 5 seconds

The key auto-expires after 5 s so "typing_stop" events are optional —
the indicator disappears on its own if the user stops typing.
"""

from app.redis.client import get_redis

_TTL = 5  # seconds — indicator vanishes if no refresh within 5 s


def _key(conversation_id: str, user_id: str) -> str:
    return f"typing:{conversation_id}:{user_id}"


async def set_typing(conversation_id: str, user_id: str) -> None:
    """Mark user as typing in a conversation."""
    r = await get_redis()
    await r.set(_key(conversation_id, user_id), "1", ex=_TTL)


async def clear_typing(conversation_id: str, user_id: str) -> None:
    """Explicitly remove the typing indicator."""
    r = await get_redis()
    await r.delete(_key(conversation_id, user_id))


async def get_typing_users(conversation_id: str) -> list[str]:
    """Return list of user_ids currently typing in a conversation.

    Uses SCAN (non-blocking, cursor-based) to find all matching keys.
    """
    r = await get_redis()
    pattern = f"typing:{conversation_id}:*"
    prefix = f"typing:{conversation_id}:"

    user_ids: list[str] = []
    async for key in r.scan_iter(match=pattern, count=100):
        user_id = key[len(prefix):]
        user_ids.append(user_id)

    return user_ids
