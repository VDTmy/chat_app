"""
User presence management via Redis.

Keys:
    user:online:{user_id}  → "1"  EX 35 seconds

Workflow:
  - set_online()   called when WebSocket connects
  - set_offline()  called when WebSocket disconnects
  - heartbeat()    called every 25 s to refresh the TTL
  - is_online()    used by API/WS to check presence without a DB query
"""

from app.redis.client import get_redis

_TTL = 35  # seconds — slightly longer than heartbeat interval (25 s)


def _key(user_id: str) -> str:
    return f"user:online:{user_id}"


async def set_online(user_id: str) -> None:
    """Mark user as online. Key expires in 35 s if not refreshed."""
    r = await get_redis()
    await r.set(_key(user_id), "1", ex=_TTL)


async def set_offline(user_id: str) -> None:
    """Immediately remove the online marker."""
    r = await get_redis()
    await r.delete(_key(user_id))


async def is_online(user_id: str) -> bool:
    """Return True if the user currently has an active presence key."""
    r = await get_redis()
    return bool(await r.exists(_key(user_id)))


async def heartbeat(user_id: str) -> None:
    """Refresh the TTL so the key doesn't expire while the user is connected."""
    r = await get_redis()
    await r.expire(_key(user_id), _TTL)
