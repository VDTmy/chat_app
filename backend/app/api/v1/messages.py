"""
/api/v1 — message endpoints (nested under conversations and standalone).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.message import MessageListResponse, MessageResponse, SendMessageRequest
from app.services.message_service import MessageService

router = APIRouter(tags=["messages"])


# ── GET /conversations/{id}/messages — paginated message list ─────────
@router.get(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
async def list_messages(
    conversation_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch messages for a conversation with cursor-based pagination."""
    service = MessageService(db)
    return await service.list_messages(
        conversation_id, current_user.id, limit=limit, cursor=cursor
    )


@router.post(
    "/api/v1/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a message via HTTP (fallback for when WebSocket is unavailable).

    Kafka publish is scheduled as a BackgroundTask so it runs AFTER the response
    is sent (and therefore after get_db has committed the transaction). This
    matches the WebSocket flow where Kafka is published post-commit.
    """
    service = MessageService(db)
    message = await service.send_message(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=body.content,
        message_type=body.message_type,
        reply_to_id=body.reply_to_id,
    )

    # Snapshot the values we need BEFORE the session is closed
    msg_id = message.id
    msg_type_val = message.message_type.value
    msg_created_at = message.created_at
    user_id = current_user.id

    async def _publish():
        from app.kafka.producer import publish_chat_event
        await publish_chat_event(
            event_type="message_sent",
            message_id=msg_id,
            user_id=user_id,
            conversation_id=conversation_id,
            message_type=msg_type_val,
            timestamp=msg_created_at,
        )

    # BackgroundTask runs after the response is fully sent → DB is already committed
    background_tasks.add_task(_publish)

    return message


# ── DELETE /messages/{id} — soft delete ───────────────────────────────
@router.delete(
    "/api/v1/messages/{message_id}",
    response_model=MessageResponse,
)
async def delete_message(
    message_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a message (sender only). Sets is_deleted=True and clears content."""
    service = MessageService(db)
    return await service.delete_message(message_id, current_user.id)


# ── GET /messages/search — full-text search ──────────────────────────
@router.get(
    "/api/v1/messages/search",
    response_model=list[MessageResponse],
)
async def search_messages(
    q: str = Query(..., min_length=1, max_length=200),
    conversation_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search messages by content. Optionally filter by conversation."""
    service = MessageService(db)
    return await service.search_messages(
        q, current_user.id, conversation_id=conversation_id
    )
