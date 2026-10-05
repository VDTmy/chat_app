"""
User service — business logic for user profile management.
"""

import uuid
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    """Operations on user profiles (not auth-related)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def get_profile(self, user_id: uuid.UUID) -> User:
        """Fetch a user by ID; raise 404 if not found."""
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def update_profile(
        self,
        user: User,
        *,
        username: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        """Update mutable profile fields for the given user."""
        if username is not None and username != user.username:
            existing = await self.repo.get_by_username(username)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username already taken",
                )
            user.username = username

        if avatar_url is not None:
            user.avatar_url = avatar_url

        await self.session.flush()
        await self.session.refresh(user)
        return user

    async def search_users(
        self,
        query: str,
        current_user_id: uuid.UUID,
        *,
        limit: int = 20,
    ) -> Sequence[User]:
        """Search users by username or email, excluding the current user."""
        pattern = f"%{query}%"
        stmt = (
            select(User)
            .where(
                User.id != current_user_id,
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                ),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
