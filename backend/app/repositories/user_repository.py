"""
User repository — data-access layer for User model.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Thin wrapper around SQLAlchemy queries for the User table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        """Return a User by email, or None if not found."""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Return a User by username, or None if not found."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return a User by primary key, or None if not found."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        username: str,
        hashed_password: str,
    ) -> User:
        """Insert a new User and return it (flushed, not yet committed)."""
        user = User(
            email=email,
            username=username,
            hashed_password=hashed_password,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
