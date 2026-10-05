"""
/ws — WebSocket endpoint for real-time chat.

Changes from v1:
  - User presence tracked via Redis (set_online / set_offline / heartbeat)
    instead of direct DB writes.
  - A background heartbeat coroutine runs alongside the message loop and
    refreshes the Redis presence key every 25 s.
  - Client can send {"type": "ping"} → server calls heartbeat() + replies pong.
  - Typing events write to Redis as well as broadcast via Pub/Sub.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.base import async_session_factory
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User
from app.redis import presence, typing as redis_typing
from app.websocket.events import (
    handle_mark_seen,
    handle_send_message,
    handle_typing_start,
    handle_typing_stop,
)
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()

_HEARTBEAT_INTERVAL = 25  # seconds — shorter than presence TTL (35 s)

# Event dispatcher table
EVENT_HANDLERS = {
    "send_message": handle_send_message,
    "typing_start": handle_typing_start,
    "typing_stop": handle_typing_stop,
    "mark_seen": handle_mark_seen,
}


# ── Auth helper ───────────────────────────────────────────────────────

async def _authenticate_ws(token: str) -> str | None:
    """Verify a JWT token and return the user_id string, or None on failure."""
    from jose import jwt as jose_jwt

    try:
        payload = jose_jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ── Friend helpers ────────────────────────────────────────────────────

async def _get_friend_ids(user_id: str) -> list[str]:
    """Return a list of accepted friend user IDs for broadcasting online/offline."""
    uid = uuid.UUID(user_id)
    async with async_session_factory() as session:
        stmt = select(Friendship).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                Friendship.requester_id == uid,
                Friendship.addressee_id == uid,
            ),
        )
        result = await session.execute(stmt)
        friendships = result.scalars().all()

        return [
            str(f.addressee_id if f.requester_id == uid else f.requester_id)
            for f in friendships
        ]


# ── DB presence helpers (last_seen) ───────────────────────────────────

async def _db_set_user_offline(user_id: str) -> None:
    """Update last_seen timestamp in DB (best-effort, non-blocking)."""
    async with async_session_factory() as session:
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.is_online = False
            user.last_seen = datetime.now(timezone.utc)
            await session.commit()


async def _db_set_user_online(user_id: str) -> None:
    """Set is_online=True in DB (kept for DB consistency)."""
    async with async_session_factory() as session:
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            user.is_online = True
            await session.commit()


# ── Heartbeat background task ─────────────────────────────────────────

async def _heartbeat_loop(user_id: str) -> None:
    """Refresh the Redis presence key every 25 s until cancelled."""
    try:
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            await presence.heartbeat(user_id)
            logger.debug("Heartbeat refreshed for user=%s", user_id)
    except asyncio.CancelledError:
        pass


# ── WebSocket endpoint ────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint for real-time chat.

    Connect with: ws://host/ws?token=<access_token>

    Client sends JSON:  {"type": "<event_type>", "payload": {...}}
    Server sends JSON:  {"type": "<event_type>", "payload": {...}}

    Special client events:
        {"type": "ping"}  →  server refreshes heartbeat + replies {"type": "pong"}
    """
    # ── Authenticate ──────────────────────────────────────────────────
    user_id = await _authenticate_ws(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # ── Connect ───────────────────────────────────────────────────────
    await manager.connect(user_id, websocket)
    heartbeat_task: asyncio.Task | None = None

    try:
        # Mark online in Redis (fast) + DB (consistency)
        await presence.set_online(user_id)
        await _db_set_user_online(user_id)

        # Start background heartbeat
        heartbeat_task = asyncio.create_task(_heartbeat_loop(user_id))

        # Notify friends that this user is now online
        friend_ids = await _get_friend_ids(user_id)
        await manager.send_to_users(friend_ids, {
            "type": "user_online",
            "payload": {"user_id": user_id},
        })

        # Check which friends are already online and send that list to the new user
        online_friend_ids = []
        for fid in friend_ids:
            if await presence.is_online(fid):
                online_friend_ids.append(fid)

        # Confirm connection to client, including the list of online friends
        await manager.send_to_user(user_id, {
            "type": "connected",
            "payload": {
                "message": "Connected successfully",
                "user_id": user_id,
                "online_friends": online_friend_ids,
            },
        })

        # ── Message loop ──────────────────────────────────────────────
        while True:
            raw = await websocket.receive_json()

            event_type = raw.get("type")
            payload = raw.get("payload", {})

            # ── Ping / pong (heartbeat from client) ───────────────────
            if event_type == "ping":
                await presence.heartbeat(user_id)
                await manager.send_to_user(user_id, {"type": "pong"})
                continue

            if not event_type:
                await manager.send_to_user(user_id, {
                    "type": "error",
                    "payload": {"message": "Missing event type"},
                })
                continue

            handler = EVENT_HANDLERS.get(event_type)
            if handler is None:
                await manager.send_to_user(user_id, {
                    "type": "error",
                    "payload": {"message": f"Unknown event type: {event_type}"},
                })
                continue

            # Each event gets its own DB session for isolation
            async with async_session_factory() as db:
                try:
                    await handler(user_id, payload, manager, db)
                except Exception as exc:
                    logger.exception("Error handling event '%s': %s", event_type, exc)
                    await manager.send_to_user(user_id, {
                        "type": "error",
                        "payload": {"message": "Internal server error"},
                    })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected normally: user=%s", user_id)
    except Exception as exc:
        logger.exception("WebSocket error: user=%s, error=%s", user_id, exc)
    finally:
        # ── Disconnect cleanup ────────────────────────────────────────
        if heartbeat_task:
            heartbeat_task.cancel()

        manager.disconnect(user_id)

        # Remove from Redis + update DB last_seen
        await presence.set_offline(user_id)
        await _db_set_user_offline(user_id)

        # Broadcast offline to friends
        try:
            friend_ids = await _get_friend_ids(user_id)
            await manager.send_to_users(friend_ids, {
                "type": "user_offline",
                "payload": {
                    "user_id": user_id,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                },
            })
        except Exception:
            logger.exception("Failed to broadcast user_offline for user=%s", user_id)
