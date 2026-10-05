"""
Pydantic V2 schemas for conversation endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserSearchResponse


# ── Request schemas ────────────────────────────────────────────────────
class CreatePrivateConversationRequest(BaseModel):
    """Body for creating a private (1-on-1) conversation."""

    user_id: uuid.UUID


class CreateGroupConversationRequest(BaseModel):
    """Body for creating a group conversation."""

    name: str = Field(min_length=1, max_length=100)
    member_ids: list[uuid.UUID] = Field(min_length=1)


class AddMemberRequest(BaseModel):
    """Body for adding a member to a group conversation."""

    user_id: uuid.UUID


# ── Nested response helpers ────────────────────────────────────────────
class ConversationMemberResponse(BaseModel):
    """A single member entry in a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    last_read_at: datetime | None = None
    joined_at: datetime
    user: UserSearchResponse


class MessageBriefResponse(BaseModel):
    """Lightweight last-message summary embedded in conversation lists."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    message_type: str
    is_deleted: bool
    created_at: datetime


# ── Response schemas ───────────────────────────────────────────────────
class ConversationResponse(BaseModel):
    """Full conversation record returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    members: list[ConversationMemberResponse] = []


class ConversationListItem(BaseModel):
    """Conversation item for the listing endpoint (includes last msg + unread)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
    members: list[ConversationMemberResponse] = []
    last_message: MessageBriefResponse | None = None
    unread_count: int = 0
