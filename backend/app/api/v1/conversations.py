"""
/api/v1/conversations — conversation management endpoints.

Cache strategy for GET / (list conversations):
  1. Check Redis key  convs:{user_id}  (TTL 60 s)
  2. Cache hit  → return cached JSON directly
  3. Cache miss → query DB → serialise with Pydantic → store in Redis → return
  Cache is invalidated by the WebSocket event handler whenever a new message
  is sent to any conversation the user belongs to.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.redis import cache as redis_cache
from app.schemas.conversation import (
    AddMemberRequest,
    ConversationListItem,
    ConversationMemberResponse,
    ConversationResponse,
    CreateGroupConversationRequest,
    CreatePrivateConversationRequest,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


# ── GET / — list conversations ────────────────────────────────────────
@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all conversations for the current user with last message + unread count.

    Results are cached in Redis for 60 seconds to reduce DB load.
    """
    user_id_str = str(current_user.id)

    # ── Cache hit ─────────────────────────────────────────────────────
    cached = await redis_cache.get_conversations_cache(user_id_str)
    if cached is not None:
        return cached  # FastAPI serialises the raw list as-is

    # ── Cache miss — query DB ──────────────────────────────────────────
    service = ConversationService(db)
    raw_list = await service.list_conversations(current_user.id)

    # Validate through Pydantic so the cached shape is always correct
    validated = [ConversationListItem.model_validate(item) for item in raw_list]
    serialisable = [item.model_dump(mode="json") for item in validated]

    await redis_cache.set_conversations_cache(user_id_str, serialisable)

    return validated


# ── POST /private — create private conversation ───────────────────────
@router.post("/private", response_model=ConversationResponse, status_code=201)
async def create_private_conversation(
    body: CreatePrivateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a private (1-on-1) conversation or return existing one."""
    service = ConversationService(db)
    return await service.create_private(current_user.id, body.user_id)


# ── POST /group — create group conversation ───────────────────────────
@router.post("/group", response_model=ConversationResponse, status_code=201)
async def create_group_conversation(
    body: CreateGroupConversationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a group conversation. Creator becomes admin."""
    service = ConversationService(db)
    return await service.create_group(
        current_user.id, body.name, body.member_ids
    )


# ── GET /{id} — conversation detail ──────────────────────────────────
@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full details of a single conversation."""
    service = ConversationService(db)
    return await service.get_conversation(conversation_id, current_user.id)


# ── POST /{id}/members — add member (group only) ─────────────────────
@router.post(
    "/{conversation_id}/members",
    response_model=ConversationMemberResponse,
    status_code=201,
)
async def add_member(
    conversation_id: uuid.UUID,
    body: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a member to a group conversation."""
    service = ConversationService(db)
    return await service.add_member(
        conversation_id, body.user_id, current_user.id
    )


# ── DELETE /{id}/members/{user_id} — remove member ───────────────────
@router.delete("/{conversation_id}/members/{user_id}", status_code=204)
async def remove_member(
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member from a conversation (admin or self-leave)."""
    service = ConversationService(db)
    await service.remove_member(conversation_id, user_id, current_user.id)


# ── PATCH /{id}/read — mark conversation as read ─────────────────────
@router.patch(
    "/{conversation_id}/read",
    response_model=ConversationMemberResponse,
)
async def mark_as_read(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update last_read_at to now for the current user in a conversation."""
    service = ConversationService(db)
    return await service.mark_as_read(conversation_id, current_user.id)
