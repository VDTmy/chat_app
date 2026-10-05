"""
Pydantic V2 schemas for friendship endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserSearchResponse


# ── Request schemas ────────────────────────────────────────────────────
class FriendRequestCreate(BaseModel):
    """Body for POST /friends/request."""

    addressee_id: uuid.UUID


# ── Response schemas ───────────────────────────────────────────────────
class FriendshipResponse(BaseModel):
    """Full friendship record returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    status: str
    created_at: datetime
    requester: UserSearchResponse
    addressee: UserSearchResponse
