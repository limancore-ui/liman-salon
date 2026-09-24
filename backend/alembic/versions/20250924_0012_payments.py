"""payments table

Revision ID: 20250924_0012
Revises: 20250924_0011
Create Date: 2025-09-24

Subscription and booking charges (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250924_0012"
down_revision: str | None = "20250924_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PAYMENT_STATUS_CHECK = (
    "status IN ('pending', 'processing', 'succeeded', 'failed', "
    "'refunded', 'partially_refunded', 'cancelled')"
)


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("subscription_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("booking_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.CHAR(length=3), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("payment_method", sa.String(length=32), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
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
            "amount_cents > 0",
            name="ck_payments_amount_cents",
        ),
        sa.CheckConstraint(_PAYMENT_STATUS_CHECK, name="ck_payments_status"),
        sa.CheckConstraint(
            "(subscription_id IS NOT NULL) OR (booking_id IS NOT NULL)",
            name="ck_payments_business_anchor",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salon_id", "subscription_id"],
            ["subscriptions.salon_id", "subscriptions.id"],
            ondelete="SET NULL",
            name="fk_payments_subscription_salon_id_subscription_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_payments_booking_salon_id_booking_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payments_salon_id_status_created_at",
        "payments",
        ["salon_id", "status", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_payments_salon_id_subscription_id",
        "payments",
        ["salon_id", "subscription_id"],
        unique=False,
        postgresql_where=sa.text("subscription_id IS NOT NULL"),
    )
    op.create_index(
        "ix_payments_booking_id",
        "payments",
        ["booking_id"],
        unique=False,
        postgresql_where=sa.text("booking_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payments_salon_id_idempotency_key",
        "payments",
        ["salon_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_payments_provider_provider_payment_id",
        "payments",
        ["provider", "provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payments_provider_provider_payment_id",
        table_name="payments",
    )
    op.drop_index(
        "uq_payments_salon_id_idempotency_key",
        table_name="payments",
    )
    op.drop_index("ix_payments_booking_id", table_name="payments")
    op.drop_index("ix_payments_salon_id_subscription_id", table_name="payments")
    op.drop_index("ix_payments_salon_id_status_created_at", table_name="payments")
    op.drop_table("payments")
