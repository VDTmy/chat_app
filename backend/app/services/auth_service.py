"""
Authentication service — business logic for register, login, refresh, logout.

Refresh token flow (with Redis):
  login()         → create token pair → store refresh token in Redis
  refresh_token() → decode JWT → verify stored token matches → rotate
  logout()        → delete Redis key → old token can never be reused
"""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.redis import tokens as redis_tokens
from app.repositories.user_repository import UserRepository


class AuthService:
    """Auth operations that sit between the API layer and the repo."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = UserRepository(session)

    # ── Register ───────────────────────────────────────────────────────
    async def register(
        self,
        email: str,
        username: str,
        password: str,
    ) -> User:
        """Create a new user after checking for duplicates."""
        if await self.repo.get_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
        if await self.repo.get_by_username(username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        hashed_pw = hash_password(password)
        return await self.repo.create(email, username, hashed_pw)

    # ── Login ──────────────────────────────────────────────────────────
    async def login(
        self,
        email: str,
        password: str,
    ) -> dict:
        """Verify credentials, return token pair, and store refresh in Redis."""
        user = await self.repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user_id = str(user.id)
        token_data = {"sub": user_id}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Persist refresh token in Redis (replaces any previous session)
        await redis_tokens.store_refresh_token(user_id, refresh_token)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    # ── Refresh ────────────────────────────────────────────────────────
    async def refresh_token(self, token: str) -> dict:
        """Validate a refresh token against Redis, then rotate to a new pair."""
        payload = decode_token(token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type — expected a refresh token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject",
            )

        # ── Verify token is still valid in Redis (not revoked) ─────────
        stored = await redis_tokens.get_refresh_token(user_id)
        if stored is None or stored != token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or is invalid",
            )

        # ── Rotate: issue new pair, store new refresh token ────────────
        token_data = {"sub": user_id}
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)

        await redis_tokens.store_refresh_token(user_id, new_refresh)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }

    # ── Logout ─────────────────────────────────────────────────────────
    async def logout(self, user_id: str) -> None:
        """Revoke the user's refresh token (true server-side revocation)."""
        await redis_tokens.revoke_refresh_token(user_id)
