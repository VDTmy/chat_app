"""
Conversation service — business logic for conversation management.
"""

import uuid
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationType
from app.models.conversation_member import ConversationMember, MemberRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.user_repository import UserRepository


class ConversationService:
    """Conversation lifecycle: create, list, members, read-tracking."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ConversationRepository(session)
        self.user_repo = UserRepository(session)

    # ── Create private ────────────────────────────────────────────────
    async def create_private(
        self,
        current_user_id: uuid.UUID,
        other_user_id: uuid.UUID,
    ) -> Conversation:
        """Create a 1-on-1 conversation, or return existing one."""
        if current_user_id == other_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create a conversation with yourself",
            )

        other = await self.user_repo.get_by_id(other_user_id)
        if other is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found",
            )

        # Check for existing private conversation
        existing = await self.repo.find_private_between(
            current_user_id, other_user_id
        )
        if existing is not None:
            return existing

        conversation = await self.repo.create(ConversationType.PRIVATE)
        await self.repo.add_member(conversation.id, current_user_id, MemberRole.MEMBER)
        await self.repo.add_member(conversation.id, other_user_id, MemberRole.MEMBER)

        # Re-fetch to get members loaded
        return await self.repo.get_by_id(conversation.id)  # type: ignore[return-value]

    # ── Create group ──────────────────────────────────────────────────
    async def create_group(
        self,
        current_user_id: uuid.UUID,
        name: str,
        member_ids: list[uuid.UUID],
    ) -> Conversation:
        """Create a group conversation. Creator is made admin."""
        # Validate all members exist
        all_ids = set(member_ids) | {current_user_id}
        for uid in all_ids:
            user = await self.user_repo.get_by_id(uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {uid} not found",
                )

        conversation = await self.repo.create(ConversationType.GROUP, name=name)

        # Creator is admin
        await self.repo.add_member(conversation.id, current_user_id, MemberRole.ADMIN)

        # Other members
        for uid in member_ids:
            if uid != current_user_id:
                await self.repo.add_member(conversation.id, uid, MemberRole.MEMBER)

        return await self.repo.get_by_id(conversation.id)  # type: ignore[return-value]

    # ── Get detail ────────────────────────────────────────────────────
    async def get_conversation(
        self,
        conversation_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Conversation:
        """Fetch a conversation — caller must be a member."""
        conversation = await self.repo.get_by_id(conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        self._assert_member(conversation, current_user_id)
        return conversation

    # ── List conversations ────────────────────────────────────────────
    async def list_conversations(self, user_id: uuid.UUID) -> list[dict]:
        """Return conversations with last_message and unread_count."""
        conversations = await self.repo.list_conversations_for_user(user_id)
        result = []
        for conv in conversations:
            last_msg = await self.repo.get_last_message(conv.id)

            # Find the member record for the current user
            member = next(
                (m for m in conv.members if m.user_id == user_id), None
            )
            last_read = member.last_read_at if member else None
            unread = await self.repo.count_unread(conv.id, last_read)

            result.append(
                {
                    "id": conv.id,
                    "type": conv.type.value,
                    "name": conv.name,
                    "avatar_url": conv.avatar_url,
                    "created_at": conv.created_at,
                    "members": conv.members,
                    "last_message": last_msg,
                    "unread_count": unread,
                }
            )
        return result

    # ── Add member (group only) ───────────────────────────────────────
    async def add_member(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> ConversationMember:
        """Add a user to a group conversation."""
        conversation = await self._get_or_404(conversation_id)
        self._assert_member(conversation, current_user_id)

        if conversation.type != ConversationType.GROUP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot add members to a private conversation",
            )

        target = await self.user_repo.get_by_id(user_id)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        existing = await self.repo.get_member(conversation_id, user_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member",
            )

        return await self.repo.add_member(conversation_id, user_id)

    # ── Remove member ─────────────────────────────────────────────────
    async def remove_member(
        self,
        conversation_id: uuid.UUID,
        target_user_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> None:
        """Remove a member from a conversation (admin or self-leave)."""
        conversation = await self._get_or_404(conversation_id)
        self._assert_member(conversation, current_user_id)

        member = await self.repo.get_member(conversation_id, target_user_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in conversation",
            )

        # Only admin or the member themselves can remove
        if target_user_id != current_user_id:
            current_member = await self.repo.get_member(
                conversation_id, current_user_id
            )
            if current_member is None or current_member.role != MemberRole.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can remove other members",
                )

        await self.repo.remove_member(member)

    # ── Mark as read ──────────────────────────────────────────────────
    async def mark_as_read(
        self,
        conversation_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> ConversationMember:
        """Update last_read_at for the current user in a conversation."""
        conversation = await self._get_or_404(conversation_id)
        self._assert_member(conversation, current_user_id)

        member = await self.repo.get_member(conversation_id, current_user_id)
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found",
            )

        return await self.repo.update_last_read(member)

    # ── Helpers ───────────────────────────────────────────────────────
    async def _get_or_404(self, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self.repo.get_by_id(conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation

    @staticmethod
    def _assert_member(conversation: Conversation, user_id: uuid.UUID) -> None:
        member_ids = {m.user_id for m in conversation.members}
        if user_id not in member_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this conversation",
            )
