"""
/api/v1/auth — authentication endpoints.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ── POST /register ────────────────────────────────────────────────────
@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account and return an access + refresh token pair.

    After creating the user, an automatic login is performed so the client
    receives tokens immediately without needing a separate /login call.
    """
    service = AuthService(db)
    await service.register(body.email, body.username, body.password)
    # Auto-login: return tokens so the frontend can proceed directly
    return await service.login(body.email, body.password)


# ── POST /login ───────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and receive access + refresh tokens.

    The refresh token is stored server-side in Redis for revocation support.
    """
    service = AuthService(db)
    return await service.login(body.email, body.password)


# ── POST /refresh ─────────────────────────────────────────────────────
@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new token pair.

    The supplied token is validated against the Redis store.  Revoked tokens
    (e.g. after logout) are rejected with 401.
    """
    service = AuthService(db)
    return await service.refresh_token(body.refresh_token)


# ── POST /logout ──────────────────────────────────────────────────────
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the current user's refresh token.

    After calling this endpoint the refresh token issued at login is
    permanently invalidated — subsequent /refresh attempts return 401.
    """
    service = AuthService(db)
    await service.logout(str(current_user.id))


# ── GET /me ────────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user
