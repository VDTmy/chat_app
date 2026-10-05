"""
Message repository — data-access layer for Message model.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageType

logger = logging.getLogger(__name__)


class MessageRepository:
    """Thin wrapper around SQLAlchemy queries for the Message table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, message_id: uuid.UUID) -> Message | None:
        """Return a Message by primary key."""
        stmt = select(Message).where(Message.id == message_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        reply_to_id: uuid.UUID | None = None,
    ) -> Message:
        """Insert a new message (flushed, not yet committed)."""
        message = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            reply_to_id=reply_to_id,
        )
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def soft_delete(self, message: Message) -> Message:
        """Mark a message as deleted (soft delete)."""
        message.is_deleted = True
        message.content = ""  # clear content on soft-delete
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        limit: int = 20,
        cursor: uuid.UUID | None = None,
    ) -> Sequence[Message]:
        """Return messages for a conversation with cursor-based pagination.

        Messages are returned newest-first. The cursor is the ID of the last
        message seen; we fetch messages older than that cursor's created_at.
        The caller should pass limit+1 via the service layer to detect has_more.
        """
        # Always filter by conversation_id — never by sender_id
        conditions = [Message.conversation_id == conversation_id]

        if cursor is not None:
            # Find the created_at of the cursor message to enable keyset pagination
            cursor_stmt = select(Message.created_at).where(Message.id == cursor)
            cursor_result = await self.session.execute(cursor_stmt)
            cursor_time = cursor_result.scalar_one_or_none()
            if cursor_time is not None:
                conditions.append(Message.created_at < cursor_time)
            else:
                logger.warning("list_messages: cursor message %s not found, ignoring cursor", cursor)

        logger.debug(
            "list_messages: conv=%s cursor=%s limit=%d",
            conversation_id, cursor, limit,
        )

        stmt = (
            select(Message)
            .where(and_(*conditions))
            .order_by(Message.created_at.desc())
            .limit(limit)  # service layer passes limit+1 to detect has_more
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        logger.debug("list_messages: returned %d rows", len(rows))
        return rows

    async def search_messages(
        self,
        query: str,
        conversation_id: uuid.UUID | None = None,
        limit: int = 30,
    ) -> Sequence[Message]:
        """Full-text search messages by content (case-insensitive LIKE)."""
        pattern = f"%{query}%"
        conditions = [
            Message.content.ilike(pattern),
            Message.is_deleted == False,  # noqa: E712
        ]
        if conversation_id is not None:
            conditions.append(Message.conversation_id == conversation_id)

        stmt = (
            select(Message)
            .where(and_(*conditions))
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
