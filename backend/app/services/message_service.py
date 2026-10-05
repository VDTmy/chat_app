"""
Message service — business logic for sending, fetching and deleting messages.
"""

import logging
import uuid
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageType
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository

logger = logging.getLogger(__name__)


class MessageService:
    """Message operations: send, list, search, soft-delete."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.msg_repo = MessageRepository(session)
        self.conv_repo = ConversationRepository(session)

    # ── Send message ──────────────────────────────────────────────────
    async def send_message(
        self,
        conversation_id: uuid.UUID,
        sender_id: uuid.UUID,
        content: str,
        message_type: str = "text",
        reply_to_id: uuid.UUID | None = None,
    ) -> Message:
        """Create a new message in a conversation (HTTP fallback)."""
        # Verify sender is a member
        await self._assert_member(conversation_id, sender_id)

        # Validate reply_to if provided
        if reply_to_id is not None:
            reply_msg = await self.msg_repo.get_by_id(reply_to_id)
            if reply_msg is None or reply_msg.conversation_id != conversation_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reply target message not found in this conversation",
                )

        msg_type = MessageType(message_type)
        return await self.msg_repo.create(
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=content,
            message_type=msg_type,
            reply_to_id=reply_to_id,
        )

    # ── List messages (cursor-based) ──────────────────────────────────
    async def list_messages(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 20,
        cursor: uuid.UUID | None = None,
    ) -> dict:
        """Return messages with cursor-based pagination (newest first)."""
        # Step 1: verify membership (direct query — no full conversation load)
        await self._assert_member(conversation_id, user_id)

        # Step 2: fetch limit+1 rows to detect has_more (repo receives the +1 explicitly)
        rows = await self.msg_repo.list_messages(
            conversation_id, limit=limit + 1, cursor=cursor
        )

        logger.debug(
            "list_messages conv=%s user=%s cursor=%s → fetched %d rows (limit=%d)",
            conversation_id, user_id, cursor, len(rows), limit,
        )

        has_more = len(rows) > limit
        # Slice to the requested page size BEFORE reading the cursor
        messages = list(rows[:limit])
        # next_cursor = ID of the LAST message on this page (oldest in newest-first order)
        next_cursor = str(messages[-1].id) if has_more and messages else None

        return {
            "messages": messages,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    # ── Soft delete ───────────────────────────────────────────────────
    async def delete_message(
        self,
        message_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Message:
        """Soft-delete a message. Only the sender can delete."""
        message = await self.msg_repo.get_by_id(message_id)
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )
        if message.sender_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the sender can delete this message",
            )
        if message.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message is already deleted",
            )
        return await self.msg_repo.soft_delete(message)

    # ── Search ────────────────────────────────────────────────────────
    async def search_messages(
        self,
        query: str,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None = None,
    ) -> Sequence[Message]:
        """Search messages by content. If conversation_id given, must be member."""
        if conversation_id is not None:
            await self._assert_member(conversation_id, user_id)

        return await self.msg_repo.search_messages(
            query, conversation_id=conversation_id
        )

    # ── Helpers ───────────────────────────────────────────────────────
    async def _assert_member(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Raise 403 if user is not a member of the conversation.

        Uses a direct targeted query (get_member) rather than loading the full
        Conversation object to avoid potential stale/empty members caused by
        circular selectin relationships in async SQLAlchemy sessions.
        """
        # First check the conversation exists
        conv = await self.conv_repo.get_by_id(conversation_id)
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        # Direct membership query — avoids relying on relationship lazy loads
        member = await self.conv_repo.get_member(conversation_id, user_id)
        logger.debug(
            "_assert_member conv=%s user=%s → member=%s",
            conversation_id, user_id, member,
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation",
            )
