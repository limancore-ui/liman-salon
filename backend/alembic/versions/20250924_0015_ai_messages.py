"""ai_messages table

Revision ID: 20250924_0015
Revises: 20250924_0014
Create Date: 2025-09-24

AI conversation messages audit log (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250924_0015"
down_revision: str | None = "20250924_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AI_MESSAGE_ROLE_CHECK = (
    "role IN ('user', 'assistant', 'system', 'tool')"
)


def upgrade() -> None:
    op.create_table(
        "ai_messages",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("conversation_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column("tool_call_id", sa.String(length=64), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_AI_MESSAGE_ROLE_CHECK, name="ck_ai_messages_role"),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salon_id", "conversation_id"],
            ["ai_conversations.salon_id", "ai_conversations.id"],
            ondelete="CASCADE",
            name="fk_ai_messages_conversation_salon_id_conversation_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_messages_salon_id_conversation_id_created_at",
        "ai_messages",
        ["salon_id", "conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_messages_salon_id_created_at",
        "ai_messages",
        ["salon_id", sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_messages_salon_id_created_at",
        table_name="ai_messages",
    )
    op.drop_index(
        "ix_ai_messages_salon_id_conversation_id_created_at",
        table_name="ai_messages",
    )
    op.drop_table("ai_messages")
