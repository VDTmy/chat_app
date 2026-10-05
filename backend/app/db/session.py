"""
Async session dependency for FastAPI.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session and ensure it is closed after use."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
