"""
WebSocket event handlers — business logic for each incoming event type.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_member import ConversationMember
from app.models.message import MessageType
from app.redis import cache as redis_cache
from app.redis import typing as redis_typing
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)


async def handle_send_message(
    user_id: str,
    payload: dict,
    manager: ConnectionManager,
    db: AsyncSession,
) -> None:
    """Handle "send_message" event: persist to DB, broadcast to conversation.

    Expected payload:
        conversation_id: str (UUID)
        content: str
        message_type: str (optional, default "text")
        reply_to_id: str | None (optional)
    """
    conv_id_str = payload.get("conversation_id")
    content = payload.get("content")
    if not conv_id_str or not content:
        await manager.send_to_user(user_id, {
            "type": "error",
            "payload": {"message": "Missing conversation_id or content"},
        })
        return

    try:
        conv_id = uuid.UUID(conv_id_str)
    except ValueError:
        await manager.send_to_user(user_id, {
            "type": "error",
            "payload": {"message": "Invalid conversation_id"},
        })
        return

    # Verify membership
    conv_repo = ConversationRepository(db)
    member = await conv_repo.get_member(conv_id, uuid.UUID(user_id))
    if member is None:
        await manager.send_to_user(user_id, {
            "type": "error",
            "payload": {"message": "You are not a member of this conversation"},
        })
        return

    # Resolve optional fields
    msg_type_str = payload.get("message_type", "text")
    try:
        msg_type = MessageType(msg_type_str)
    except ValueError:
        msg_type = MessageType.TEXT

    reply_to_id = None
    reply_str = payload.get("reply_to_id")
    if reply_str:
        try:
            reply_to_id = uuid.UUID(reply_str)
        except ValueError:
            pass

    # Persist
    msg_repo = MessageRepository(db)
    message = await msg_repo.create(
        conversation_id=conv_id,
        sender_id=uuid.UUID(user_id),
        content=content,
        message_type=msg_type,
        reply_to_id=reply_to_id,
    )
    await db.commit()

    # ── Publish event to Kafka for streaming analytics ─────────────────
    # This happens AFTER the DB commit — the message is safely persisted.
    # Kafka publish is fire-and-forget: errors are logged, never propagated.
    from app.kafka.producer import publish_chat_event  # local import avoids circular deps

    await publish_chat_event(
        event_type="message_sent",
        message_id=message.id,
        user_id=uuid.UUID(user_id),
        conversation_id=conv_id,
        message_type=message.message_type.value,
        timestamp=message.created_at,
    )

    # ── Invalidate conversation list cache for all members ─────────────
    stmt = select(ConversationMember.user_id).where(
        ConversationMember.conversation_id == conv_id
    )
    result = await db.execute(stmt)
    member_ids = [str(uid) for uid in result.scalars().all()]
    await redis_cache.invalidate_many(member_ids)

    # Broadcast to all conversation members via Redis Pub/Sub
    broadcast_data = {
        "type": "new_message",
        "payload": {
            "id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "sender_id": str(message.sender_id),
            "content": message.content,
            "message_type": message.message_type.value,
            "reply_to_id": str(message.reply_to_id) if message.reply_to_id else None,
            "is_deleted": message.is_deleted,
            "created_at": message.created_at.isoformat(),
        },
    }
    await manager.broadcast_to_conversation(conv_id, broadcast_data, db)


async def handle_typing_start(
    user_id: str,
    payload: dict,
    manager: ConnectionManager,
    db: AsyncSession,
) -> None:
    """Handle "typing_start" event: store in Redis + broadcast indicator.

    Expected payload:
        conversation_id: str (UUID)
    """
    conv_id_str = payload.get("conversation_id")
    if not conv_id_str:
        return

    try:
        conv_id = uuid.UUID(conv_id_str)
    except ValueError:
        return

    # Store typing state in Redis (auto-expires in 5 s)
    await redis_typing.set_typing(conv_id_str, user_id)

    broadcast_data = {
        "type": "typing_start",
        "payload": {
            "user_id": user_id,
            "conversation_id": conv_id_str,
        },
    }
    await manager.broadcast_to_conversation(
        conv_id, broadcast_data, db, exclude_user_id=user_id
    )


async def handle_typing_stop(
    user_id: str,
    payload: dict,
    manager: ConnectionManager,
    db: AsyncSession,
) -> None:
    """Handle "typing_stop" event: clear Redis + broadcast stop indicator.

    Expected payload:
        conversation_id: str (UUID)
    """
    conv_id_str = payload.get("conversation_id")
    if not conv_id_str:
        return

    try:
        conv_id = uuid.UUID(conv_id_str)
    except ValueError:
        return

    # Remove typing state from Redis
    await redis_typing.clear_typing(conv_id_str, user_id)

    broadcast_data = {
        "type": "typing_stop",
        "payload": {
            "user_id": user_id,
            "conversation_id": conv_id_str,
        },
    }
    await manager.broadcast_to_conversation(
        conv_id, broadcast_data, db, exclude_user_id=user_id
    )


async def handle_mark_seen(
    user_id: str,
    payload: dict,
    manager: ConnectionManager,
    db: AsyncSession,
) -> None:
    """Handle "mark_seen" event: update last_read_at and broadcast to conversation.

    Expected payload:
        conversation_id: str (UUID)
    """
    conv_id_str = payload.get("conversation_id")
    if not conv_id_str:
        return

    try:
        conv_id = uuid.UUID(conv_id_str)
    except ValueError:
        return

    conv_repo = ConversationRepository(db)
    member = await conv_repo.get_member(conv_id, uuid.UUID(user_id))
    if member is None:
        return

    now = datetime.now(timezone.utc)
    await conv_repo.update_last_read(member)
    await db.commit()

    broadcast_data = {
        "type": "message_seen",
        "payload": {
            "conversation_id": conv_id_str,
            "user_id": user_id,
            "seen_at": now.isoformat(),
        },
    }
    await manager.broadcast_to_conversation(
        conv_id, broadcast_data, db, exclude_user_id=user_id
    )
