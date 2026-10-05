"""
Conversation SQLAlchemy model.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ConversationType(str, enum.Enum):
    """Whether the conversation is 1-on-1 or a group chat."""

    PRIVATE = "private"
    GROUP = "group"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    type: Mapped[ConversationType] = mapped_column(
        Enum(ConversationType, name="conversation_type", create_constraint=True),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────
    members = relationship(
        "ConversationMember",
        back_populates="conversation",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "Message",
        back_populates="conversation",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} [{self.type.value}]>"
