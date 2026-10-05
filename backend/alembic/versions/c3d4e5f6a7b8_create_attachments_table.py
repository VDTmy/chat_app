"""create attachments table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-25 08:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use IF NOT EXISTS to be idempotent in case a partial migration ran before
    op.execute("""
        CREATE TABLE IF NOT EXISTS attachments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
            file_url VARCHAR(2048) NOT NULL,
            file_name VARCHAR(512) NOT NULL,
            file_type VARCHAR(128) NOT NULL,
            file_size BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_attachments_message_id ON attachments (message_id)"
    )


def downgrade() -> None:
    op.drop_index('ix_attachments_message_id', table_name='attachments')
    op.drop_table('attachments')
