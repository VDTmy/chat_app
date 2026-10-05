"""
Refresh token storage in Redis.

Key:  refresh:{user_id}
TTL:  604800 seconds (7 days)

Storing the token in Redis allows true revocation:
  - Login    → store token
  - Refresh  → verify stored token matches; rotate to new token
  - Logout   → delete key → old token rejected on next use
"""

from typing import Optional

from app.redis.client import get_redis

_TTL = 60 * 60 * 24 * 7  # 7 days in seconds


def _key(user_id: str) -> str:
    return f"refresh:{user_id}"


async def store_refresh_token(user_id: str, token: str) -> None:
    """Persist a refresh token for *user_id*, replacing any existing one."""
    r = await get_redis()
    await r.set(_key(user_id), token, ex=_TTL)


async def get_refresh_token(user_id: str) -> Optional[str]:
    """Return the stored refresh token, or None if absent / expired."""
    r = await get_redis()
    return await r.get(_key(user_id))


async def revoke_refresh_token(user_id: str) -> None:
    """Delete the refresh token, effectively logging the user out."""
    r = await get_redis()
    await r.delete(_key(user_id))
