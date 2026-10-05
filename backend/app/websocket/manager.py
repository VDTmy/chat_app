"""
WebSocket connection manager — tracks local connections and routes messages
via Redis Pub/Sub for multi-server support.

Architecture:
  ┌──────────────┐   PUBLISH   ┌───────────────────┐   SUBSCRIBE
  │  Event       │ ──────────► │  Redis channel    │ ──────────────►
  │  handler     │             │  conversation:*   │                │
  └──────────────┘             └───────────────────┘                │
                                                                     ▼
                                                         ┌────────────────────┐
                                                         │  Background        │
                                                         │  subscriber task   │
                                                         │  (_redis_listener) │
                                                         └────────┬───────────┘
                                                                  │ _deliver_local()
                                                                  ▼
                                                         ┌────────────────────┐
                                                         │  Local WebSocket   │
                                                         │  connections       │
                                                         └────────────────────┘
"""

import asyncio
import logging
import uuid

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_member import ConversationMember

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections keyed by user_id (str).

    Broadcasting is done via Redis Pub/Sub so all server instances receive
    the message and can forward it to their locally-connected clients.
    """

    def __init__(self) -> None:
        # user_id (str) → WebSocket
        self._connections: dict[str, WebSocket] = {}
        # Background task handle for the Redis subscriber
        self._subscriber_task: asyncio.Task | None = None

    # ── Connection lifecycle ──────────────────────────────────────────

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Accept and store a WebSocket connection."""
        await websocket.accept()
        self._connections[user_id] = websocket
        logger.info("WS connected: user=%s (total=%d)", user_id, len(self._connections))

    def disconnect(self, user_id: str) -> None:
        """Remove a WebSocket connection."""
        self._connections.pop(user_id, None)
        logger.info("WS disconnected: user=%s (total=%d)", user_id, len(self._connections))

    def is_connected_locally(self, user_id: str) -> bool:
        """Check if a user has an active WebSocket connection on THIS instance."""
        return user_id in self._connections

    @property
    def online_user_ids(self) -> set[str]:
        """Return a set of all locally-connected user IDs."""
        return set(self._connections.keys())

    # ── Sending messages ──────────────────────────────────────────────

    async def send_to_user(self, user_id: str, data: dict) -> None:
        """Send a JSON payload to a specific user if they are locally connected."""
        ws = self._connections.get(user_id)
        if ws is not None:
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning("Failed to send to user=%s, removing connection", user_id)
                self.disconnect(user_id)

    async def broadcast_to_conversation(
        self,
        conversation_id: uuid.UUID,
        data: dict,
        db: AsyncSession,
        exclude_user_id: str | None = None,
    ) -> None:
        """Publish a JSON payload to Redis so ALL server instances deliver it.

        The actual delivery to WebSocket connections is handled by the
        background _redis_listener task on each instance.
        """
        from app.redis import pubsub  # local import avoids circular deps at module load

        channel = pubsub.conversation_channel(str(conversation_id))

        # Embed exclusion info inside the payload so subscribers can filter
        envelope = {
            "exclude_user_id": exclude_user_id,
            "data": data,
        }
        await pubsub.publish(channel, envelope)

    async def send_to_users(
        self,
        user_ids: list[str],
        data: dict,
        exclude_user_id: str | None = None,
    ) -> None:
        """Send a JSON payload directly to a list of locally-connected user IDs."""
        for uid in user_ids:
            if uid == exclude_user_id:
                continue
            await self.send_to_user(uid, data)

    # ── Redis Pub/Sub background subscriber ───────────────────────────

    async def _deliver_local(self, channel: str, envelope: dict) -> None:
        """Forward a Redis Pub/Sub message to all locally-connected clients.

        The channel is "conversation:{conversation_id}".  We need to look up
        conversation members from the DB to know which local connections
        should receive the message.
        """
        from app.db.base import async_session_factory

        conv_id_str = channel.split(":", 1)[-1]  # strip "conversation:" prefix
        exclude = envelope.get("exclude_user_id")
        data = envelope.get("data", {})

        try:
            conv_id = uuid.UUID(conv_id_str)
        except ValueError:
            logger.warning("Invalid conversation_id in Pub/Sub channel: %s", channel)
            return

        async with async_session_factory() as session:
            stmt = select(ConversationMember.user_id).where(
                ConversationMember.conversation_id == conv_id
            )
            result = await session.execute(stmt)
            member_ids = result.scalars().all()

        for uid in member_ids:
            uid_str = str(uid)
            if uid_str == exclude:
                continue
            await self.send_to_user(uid_str, data)

    async def start_redis_subscriber(self) -> None:
        """Launch the background task that listens on 'conversation:*'."""
        if self._subscriber_task is not None and not self._subscriber_task.done():
            return  # already running
        self._subscriber_task = asyncio.create_task(self._redis_listener())
        logger.info("Redis Pub/Sub subscriber task started")

    async def stop_redis_subscriber(self) -> None:
        """Cancel the background subscriber task."""
        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        logger.info("Redis Pub/Sub subscriber task stopped")

    async def _redis_listener(self) -> None:
        """Background coroutine: subscribe to all conversation:* channels.

        Automatically reconnects with exponential backoff if Redis is
        temporarily unavailable (e.g. server restart, network blip).
        """
        from app.redis import pubsub  # local import

        logger.info("Redis subscriber: listening on conversation:*")
        backoff = 1  # seconds
        max_backoff = 30

        while True:
            try:
                backoff = 1  # reset on successful connection
                async for channel, envelope in pubsub.subscribe_pattern("conversation:*"):
                    try:
                        await self._deliver_local(channel, envelope)
                    except Exception as exc:
                        logger.exception("Error delivering Pub/Sub message: %s", exc)
            except asyncio.CancelledError:
                logger.info("Redis subscriber: cancelled")
                raise
            except Exception as exc:
                logger.warning(
                    "Redis subscriber disconnected (%s). Retrying in %ds…", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)


# ── Singleton instance ────────────────────────────────────────────────
manager = ConnectionManager()
