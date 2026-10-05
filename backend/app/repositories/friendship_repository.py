"""
Friendship repository — data-access layer for Friendship model.
"""

import uuid
from typing import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friendship import Friendship, FriendshipStatus


class FriendshipRepository:
    """Thin wrapper around SQLAlchemy queries for the Friendship table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, friendship_id: uuid.UUID) -> Friendship | None:
        """Return a Friendship by primary key, or None if not found."""
        stmt = select(Friendship).where(Friendship.id == friendship_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_between_users(
        self,
        user_a: uuid.UUID,
        user_b: uuid.UUID,
    ) -> Friendship | None:
        """Return an existing friendship (in either direction) between two users."""
        stmt = select(Friendship).where(
            or_(
                (Friendship.requester_id == user_a) & (Friendship.addressee_id == user_b),
                (Friendship.requester_id == user_b) & (Friendship.addressee_id == user_a),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        requester_id: uuid.UUID,
        addressee_id: uuid.UUID,
    ) -> Friendship:
        """Insert a new pending friendship request."""
        friendship = Friendship(
            requester_id=requester_id,
            addressee_id=addressee_id,
            status=FriendshipStatus.PENDING,
        )
        self.session.add(friendship)
        await self.session.flush()
        await self.session.refresh(friendship)
        return friendship

    async def update_status(
        self,
        friendship: Friendship,
        status: FriendshipStatus,
    ) -> Friendship:
        """Update the status of an existing friendship."""
        friendship.status = status
        await self.session.flush()
        await self.session.refresh(friendship)
        return friendship

    async def delete(self, friendship: Friendship) -> None:
        """Delete a friendship record."""
        await self.session.delete(friendship)
        await self.session.flush()

    async def list_accepted(self, user_id: uuid.UUID) -> Sequence[Friendship]:
        """Return all accepted friendships involving the given user."""
        stmt = select(Friendship).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_pending_for_user(self, user_id: uuid.UUID) -> Sequence[Friendship]:
        """Return pending requests *received* by the given user."""
        stmt = select(Friendship).where(
            Friendship.status == FriendshipStatus.PENDING,
            Friendship.addressee_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
