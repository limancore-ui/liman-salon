"""ai_conversations table

Revision ID: 20250924_0014
Revises: 20250924_0013
Create Date: 2025-09-24

AI assistant session audit log (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250924_0014"
down_revision: str | None = "20250924_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "channel",
            sa.String(length=32),
            server_default=sa.text("'dashboard'"),
            nullable=False,
        ),
        sa.Column("external_thread_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="SET NULL",
            name="fk_ai_conversations_customer_salon_id_customer_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_ai_conversations_salon_id_id"),
    )
    op.create_index(
        "ix_ai_conversations_salon_id_last_message_at",
        "ai_conversations",
        ["salon_id", sa.text("last_message_at DESC NULLS LAST")],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversations_salon_id_user_id",
        "ai_conversations",
        ["salon_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_conversations_external_thread_id",
        "ai_conversations",
        ["external_thread_id"],
        unique=False,
        postgresql_where=sa.text("external_thread_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_conversations_external_thread_id",
        table_name="ai_conversations",
    )
    op.drop_index(
        "ix_ai_conversations_salon_id_user_id",
        table_name="ai_conversations",
    )
    op.drop_index(
        "ix_ai_conversations_salon_id_last_message_at",
        table_name="ai_conversations",
    )
    op.drop_table("ai_conversations")
