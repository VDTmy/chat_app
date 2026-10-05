"""
Conversation repository — data-access layer for Conversation & ConversationMember.
"""

import uuid
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, ConversationType
from app.models.conversation_member import ConversationMember, MemberRole
from app.models.message import Message


class ConversationRepository:
    """Data-access for conversations and their members."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Conversation CRUD ─────────────────────────────────────────────

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        """Return a Conversation with its members eagerly loaded."""
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.members))
            .where(Conversation.id == conversation_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        conv_type: ConversationType,
        name: str | None = None,
        avatar_url: str | None = None,
    ) -> Conversation:
        """Insert a new Conversation."""
        conversation = Conversation(
            type=conv_type,
            name=name,
            avatar_url=avatar_url,
        )
        self.session.add(conversation)
        await self.session.flush()
        await self.session.refresh(conversation)
        return conversation

    async def find_private_between(
        self,
        user_a: uuid.UUID,
        user_b: uuid.UUID,
    ) -> Conversation | None:
        """Find an existing private conversation between exactly two users."""
        # Sub-query: conversation IDs where both users are members
        member_a = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_a)
            .subquery()
        )
        member_b = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_b)
            .subquery()
        )

        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.members))
            .where(
                Conversation.type == ConversationType.PRIVATE,
                Conversation.id.in_(select(member_a.c.conversation_id)),
                Conversation.id.in_(select(member_b.c.conversation_id)),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Member CRUD ───────────────────────────────────────────────────

    async def add_member(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        role: MemberRole = MemberRole.MEMBER,
    ) -> ConversationMember:
        """Add a user to a conversation."""
        member = ConversationMember(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def get_member(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ConversationMember | None:
        """Return a membership record, or None."""
        stmt = select(ConversationMember).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def remove_member(self, member: ConversationMember) -> None:
        """Delete a membership record."""
        await self.session.delete(member)
        await self.session.flush()

    async def update_last_read(
        self,
        member: ConversationMember,
    ) -> ConversationMember:
        """Set last_read_at to now for the given member."""
        member.last_read_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    # ── Listing ───────────────────────────────────────────────────────

    async def list_conversations_for_user(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[Conversation]:
        """Return all conversations that a user belongs to, ordered by created_at desc."""
        user_convs = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id)
            .subquery()
        )
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.members))
            .where(Conversation.id.in_(select(user_convs.c.conversation_id)))
            .order_by(Conversation.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_last_message(
        self,
        conversation_id: uuid.UUID,
    ) -> Message | None:
        """Return the most recent message in a conversation."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_unread(
        self,
        conversation_id: uuid.UUID,
        last_read_at: datetime | None,
    ) -> int:
        """Count messages in a conversation created after last_read_at."""
        conditions = [Message.conversation_id == conversation_id]
        if last_read_at is not None:
            conditions.append(Message.created_at > last_read_at)
        stmt = select(func.count()).select_from(Message).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return result.scalar_one()
