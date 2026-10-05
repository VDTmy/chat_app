"""
Pydantic V2 schemas for user management endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ────────────────────────────────────────────────────
class UserUpdateRequest(BaseModel):
    """Body for PATCH /users/me — all fields optional."""

    username: str | None = Field(None, min_length=3, max_length=50)
    avatar_url: str | None = Field(None, max_length=500)


# ── Response schemas ───────────────────────────────────────────────────
class UserResponse(BaseModel):
    """Public representation of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    avatar_url: str | None = None
    is_online: bool
    last_seen: datetime | None = None
    created_at: datetime


class UserSearchResponse(BaseModel):
    """Lightweight user info returned in search results."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    avatar_url: str | None = None
    is_online: bool
