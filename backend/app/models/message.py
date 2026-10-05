"""
Message SQLAlchemy model.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageType(str, enum.Enum):
    """Kind of content a message carries."""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type", create_constraint=True),
        nullable=False,
        default=MessageType.TEXT,
    )
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────
    conversation = relationship("Conversation", back_populates="messages", lazy="noload")
    sender = relationship("User", lazy="selectin")
    reply_to = relationship("Message", remote_side="Message.id", lazy="selectin")
    attachments = relationship("Attachment", back_populates="message", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Message {self.id} by={self.sender_id}>"
