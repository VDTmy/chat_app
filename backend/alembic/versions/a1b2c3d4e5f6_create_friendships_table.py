"""create friendships table

Revision ID: a1b2c3d4e5f6
Revises: 5bf4fd9c5cd5
Create Date: 2026-06-16 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5bf4fd9c5cd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('friendships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('requester_id', sa.UUID(), nullable=False),
        sa.Column('addressee_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ACCEPTED', 'BLOCKED', name='friendship_status', create_constraint=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['addressee_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('requester_id', 'addressee_id', name='uq_requester_addressee'),
    )
    op.create_index(op.f('ix_friendships_requester_id'), 'friendships', ['requester_id'])
    op.create_index(op.f('ix_friendships_addressee_id'), 'friendships', ['addressee_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_friendships_addressee_id'), table_name='friendships')
    op.drop_index(op.f('ix_friendships_requester_id'), table_name='friendships')
    op.drop_table('friendships')

    # Drop the enum type
    sa.Enum(name='friendship_status').drop(op.get_bind(), checkfirst=True)
