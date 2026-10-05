"""create conversations, conversation_members, messages tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17 00:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── conversations ─────────────────────────────────────────────────
    op.create_table('conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('type', sa.Enum('PRIVATE', 'GROUP', name='conversation_type', create_constraint=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── conversation_members ──────────────────────────────────────────
    op.create_table('conversation_members',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'MEMBER', name='member_role', create_constraint=True), nullable=False),
        sa.Column('last_read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'user_id', name='uq_conversation_user'),
    )
    op.create_index(op.f('ix_conversation_members_conversation_id'), 'conversation_members', ['conversation_id'])
    op.create_index(op.f('ix_conversation_members_user_id'), 'conversation_members', ['user_id'])

    # ── messages ──────────────────────────────────────────────────────
    op.create_table('messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', sa.Enum('TEXT', 'IMAGE', 'FILE', name='message_type', create_constraint=True), nullable=False),
        sa.Column('reply_to_id', sa.UUID(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reply_to_id'], ['messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_conversation_id'), 'messages', ['conversation_id'])
    op.create_index(op.f('ix_messages_sender_id'), 'messages', ['sender_id'])
    op.create_index(op.f('ix_messages_created_at'), 'messages', ['created_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop in reverse dependency order
    op.drop_index(op.f('ix_messages_created_at'), table_name='messages')
    op.drop_index(op.f('ix_messages_sender_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_conversation_id'), table_name='messages')
    op.drop_table('messages')

    op.drop_index(op.f('ix_conversation_members_user_id'), table_name='conversation_members')
    op.drop_index(op.f('ix_conversation_members_conversation_id'), table_name='conversation_members')
    op.drop_table('conversation_members')

    op.drop_table('conversations')

    # Drop enum types
    sa.Enum(name='message_type').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='member_role').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='conversation_type').drop(op.get_bind(), checkfirst=True)
