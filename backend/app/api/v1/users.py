"""
/api/v1/users — user profile & search endpoints.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserSearchResponse, UserUpdateRequest
from app.services.user_service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ── GET /me ───────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user


# ── PATCH /me ─────────────────────────────────────────────────────────
@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the current user's username and/or avatar_url."""
    service = UserService(db)
    return await service.update_profile(
        current_user,
        username=body.username,
        avatar_url=body.avatar_url,
    )


# ── GET /search ───────────────────────────────────────────────────────
@router.get("/search", response_model=list[UserSearchResponse])
async def search_users(
    q: str = Query(..., min_length=1, max_length=100, description="Search keyword"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search users by username or email (excludes current user)."""
    service = UserService(db)
    return await service.search_users(q, current_user.id)


# ── GET /{user_id} ────────────────────────────────────────────────────
@router.get("/{user_id}", response_model=UserResponse)
async def get_user_profile(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """View another user's public profile."""
    service = UserService(db)
    return await service.get_profile(user_id)
