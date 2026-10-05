"""
Attachment SQLAlchemy model.

Stores metadata for files uploaded to MinIO and associated with a message.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────
    message = relationship("Message", back_populates="attachments", lazy="noload")

    def __repr__(self) -> str:
        return f"<Attachment {self.id} file={self.file_name}>"
