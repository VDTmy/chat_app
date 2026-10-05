"""
Pydantic V2 schemas for message endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserSearchResponse


# ── Request schemas ────────────────────────────────────────────────────
class SendMessageRequest(BaseModel):
    """Body for POST /conversations/{id}/messages."""

    content: str = Field(min_length=1, max_length=5000)
    message_type: str = Field(default="text", pattern=r"^(text|image|file)$")
    reply_to_id: uuid.UUID | None = None


# ── Response schemas ───────────────────────────────────────────────────
class MessageResponse(BaseModel):
    """Full message record returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    content: str
    message_type: str
    reply_to_id: uuid.UUID | None = None
    is_deleted: bool
    created_at: datetime
    sender: UserSearchResponse
    reply_to: "MessageResponse | None" = None


class MessageListResponse(BaseModel):
    """Paginated message list with cursor."""

    messages: list[MessageResponse]
    next_cursor: str | None = None
    has_more: bool = False
