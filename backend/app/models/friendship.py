"""
Friendship SQLAlchemy model.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FriendshipStatus(str, enum.Enum):
    """Possible states of a friendship request."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class Friendship(Base):
    __tablename__ = "friendships"

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_requester_addressee"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, name="friendship_status", create_constraint=True),
        nullable=False,
        default=FriendshipStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────
    requester = relationship("User", foreign_keys=[requester_id], lazy="selectin")
    addressee = relationship("User", foreign_keys=[addressee_id], lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<Friendship {self.requester_id} → {self.addressee_id} "
            f"[{self.status.value}]>"
        )
