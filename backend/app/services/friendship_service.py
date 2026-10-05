"""
Friendship service — business logic for friend requests and management.
"""

import uuid
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendship import Friendship, FriendshipStatus
from app.repositories.friendship_repository import FriendshipRepository
from app.repositories.user_repository import UserRepository


class FriendshipService:
    """Friend-request workflow: send, accept, reject/unfriend, list."""

    def __init__(self, session: AsyncSession) -> None:
        self.friendship_repo = FriendshipRepository(session)
        self.user_repo = UserRepository(session)

    # ── Send request ──────────────────────────────────────────────────
    async def send_request(
        self,
        requester_id: uuid.UUID,
        addressee_id: uuid.UUID,
    ) -> Friendship:
        """Create a pending friend request."""
        if requester_id == addressee_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot send a friend request to yourself",
            )

        # Ensure addressee exists
        addressee = await self.user_repo.get_by_id(addressee_id)
        if addressee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found",
            )

        # Check for existing relationship (either direction)
        existing = await self.friendship_repo.get_between_users(
            requester_id, addressee_id
        )
        if existing is not None:
            if existing.status == FriendshipStatus.ACCEPTED:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Already friends",
                )
            if existing.status == FriendshipStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Friend request already pending",
                )
            if existing.status == FriendshipStatus.BLOCKED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot send request — relationship is blocked",
                )

        return await self.friendship_repo.create(requester_id, addressee_id)

    # ── Accept request ────────────────────────────────────────────────
    async def accept_request(
        self,
        friendship_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Friendship:
        """Accept a pending friend request (only the addressee can accept)."""
        friendship = await self._get_friendship_or_404(friendship_id)

        if friendship.addressee_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the addressee can accept a friend request",
            )
        if friendship.status != FriendshipStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot accept a request with status '{friendship.status.value}'",
            )

        return await self.friendship_repo.update_status(
            friendship, FriendshipStatus.ACCEPTED
        )

    # ── Reject / Unfriend ─────────────────────────────────────────────
    async def remove_friendship(
        self,
        friendship_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> None:
        """Delete a friendship — works for rejecting pending or unfriending."""
        friendship = await self._get_friendship_or_404(friendship_id)

        # Either party can delete
        if current_user_id not in (friendship.requester_id, friendship.addressee_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not part of this friendship",
            )

        await self.friendship_repo.delete(friendship)

    # ── List accepted friends ─────────────────────────────────────────
    async def list_friends(self, user_id: uuid.UUID) -> Sequence[Friendship]:
        """Return all accepted friendships for the given user."""
        return await self.friendship_repo.list_accepted(user_id)

    # ── List pending requests ─────────────────────────────────────────
    async def list_pending(self, user_id: uuid.UUID) -> Sequence[Friendship]:
        """Return pending requests received by the given user."""
        return await self.friendship_repo.list_pending_for_user(user_id)

    # ── Helpers ───────────────────────────────────────────────────────
    async def _get_friendship_or_404(self, friendship_id: uuid.UUID) -> Friendship:
        friendship = await self.friendship_repo.get_by_id(friendship_id)
        if friendship is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friendship not found",
            )
        return friendship
