"""
ConversationMember SQLAlchemy model — join table between users and conversations.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MemberRole(str, enum.Enum):
    """Role of a user inside a conversation."""

    ADMIN = "admin"
    MEMBER = "member"


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "user_id", name="uq_conversation_user"
        ),
    )

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
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role", create_constraint=True),
        nullable=False,
        default=MemberRole.MEMBER,
    )
    last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────
    conversation = relationship(
        "Conversation", back_populates="members", lazy="selectin"
    )
    user = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<ConversationMember user={self.user_id} "
            f"conv={self.conversation_id} [{self.role.value}]>"
        )
