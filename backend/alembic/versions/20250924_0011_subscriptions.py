"""subscriptions table

Revision ID: 20250924_0011
Revises: 20250924_0010
Create Date: 2025-09-24

Salon-level SaaS subscription (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250924_0011"
down_revision: str | None = "20250924_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBSCRIPTION_STATUS_CHECK = (
    "status IN ('trialing', 'active', 'past_due', 'cancelled', 'expired')"
)


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'trialing'"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("provider_subscription_id", sa.String(length=255), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _SUBSCRIPTION_STATUS_CHECK,
            name="ck_subscriptions_status",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_subscriptions_salon_id_id"),
    )
    op.create_index(
        "uq_subscriptions_provider_provider_subscription_id",
        "subscriptions",
        ["provider", "provider_subscription_id"],
        unique=True,
        postgresql_where=sa.text("provider_subscription_id IS NOT NULL"),
    )
    op.create_index(
        "uq_subscriptions_salon_id_active_status",
        "subscriptions",
        ["salon_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('trialing', 'active', 'past_due')"
        ),
    )
    op.create_index(
        "ix_subscriptions_salon_id_status",
        "subscriptions",
        ["salon_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_subscriptions_status_current_period_end",
        "subscriptions",
        ["status", "current_period_end"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscriptions_status_current_period_end",
        table_name="subscriptions",
    )
    op.drop_index("ix_subscriptions_salon_id_status", table_name="subscriptions")
    op.drop_index("uq_subscriptions_salon_id_active_status", table_name="subscriptions")
    op.drop_index(
        "uq_subscriptions_provider_provider_subscription_id",
        table_name="subscriptions",
    )
    op.drop_table("subscriptions")
