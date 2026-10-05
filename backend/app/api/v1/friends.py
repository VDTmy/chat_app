"""
/api/v1/friends — friend-request & friendship management endpoints.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.friendship import FriendRequestCreate, FriendshipResponse
from app.services.friendship_service import FriendshipService

router = APIRouter(prefix="/api/v1/friends", tags=["friends"])


# ── POST /request — send a friend request ─────────────────────────────
@router.post("/request", response_model=FriendshipResponse, status_code=201)
async def send_friend_request(
    body: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a friend request to another user."""
    service = FriendshipService(db)
    return await service.send_request(current_user.id, body.addressee_id)


# ── PATCH /{friendship_id}/accept ─────────────────────────────────────
@router.patch("/{friendship_id}/accept", response_model=FriendshipResponse)
async def accept_friend_request(
    friendship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a pending friend request (addressee only)."""
    service = FriendshipService(db)
    return await service.accept_request(friendship_id, current_user.id)


# ── DELETE /{friendship_id} — reject or unfriend ──────────────────────
@router.delete("/{friendship_id}", status_code=204)
async def remove_friendship(
    friendship_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending request or remove an existing friendship."""
    service = FriendshipService(db)
    await service.remove_friendship(friendship_id, current_user.id)


# ── GET / — list accepted friends ─────────────────────────────────────
@router.get("", response_model=list[FriendshipResponse])
async def list_friends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all accepted friends for the current user."""
    service = FriendshipService(db)
    return await service.list_friends(current_user.id)


# ── GET /pending — list incoming pending requests ─────────────────────
@router.get("/pending", response_model=list[FriendshipResponse])
async def list_pending_requests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pending friend requests received by the current user."""
    service = FriendshipService(db)
    return await service.list_pending(current_user.id)
