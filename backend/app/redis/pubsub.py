"""
Redis Pub/Sub wrapper for broadcasting messages across server instances.

Channel naming convention:
    conversation:{conversation_id}

Usage — publisher side:
    from app.redis import pubsub
    await pubsub.publish("conversation:abc-123", {"type": "new_message", ...})

Usage — subscriber side (async generator):
    async for message in pubsub.subscribe("conversation:abc-123"):
        process(message)

For the ConnectionManager's background subscriber we use pattern subscribe
on "conversation:*" so a single subscriber task handles all channels.
"""

import json
import logging
from collections.abc import AsyncGenerator

# pyrefly: ignore [missing-import]
import redis.asyncio as aioredis

from app.redis.client import get_redis

logger = logging.getLogger(__name__)


def conversation_channel(conversation_id: str) -> str:
    """Return the standard Redis channel name for a conversation."""
    return f"conversation:{conversation_id}"


async def publish(channel: str, data: dict) -> None:
    """Publish a JSON-encoded dict to a Redis channel."""
    r = await get_redis()
    payload = json.dumps(data, default=str)
    await r.publish(channel, payload)


async def subscribe(channel: str) -> AsyncGenerator[dict, None]:
    """Async generator that yields decoded dicts received on *channel*.

    Creates a **separate** connection for the subscriber (required by Redis
    protocol — a connection in subscribe mode cannot issue other commands).
    """
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for raw in pubsub.listen():
            if raw["type"] == "message":
                try:
                    yield json.loads(raw["data"])
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Bad Pub/Sub payload on %s: %s", channel, exc)
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception as exc:
            logger.debug("Error unsubscribing from %s: %s", channel, exc)
        await pubsub.aclose()


async def subscribe_pattern(pattern: str) -> AsyncGenerator[tuple[str, dict], None]:
    """Async generator that yields (channel, data) for a glob pattern.

    Used by ConnectionManager to listen on all conversation:* channels with
    a single subscriber connection.
    """
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.psubscribe(pattern)
    try:
        async for raw in pubsub.listen():
            if raw["type"] == "pmessage":
                channel: str = raw["channel"]
                try:
                    data = json.loads(raw["data"])
                    yield channel, data
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Bad Pub/Sub payload on %s: %s", channel, exc)
    finally:
        try:
            await pubsub.punsubscribe(pattern)
        except Exception as exc:
            logger.debug("Error unsubscribing from pattern %s: %s", pattern, exc)
        await pubsub.aclose()
