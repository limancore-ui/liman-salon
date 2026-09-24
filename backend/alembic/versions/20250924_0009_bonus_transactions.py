"""bonus_transactions table

Revision ID: 20250924_0009
Revises: 20250924_0008
Create Date: 2025-09-24

Salon-scoped loyalty ledger (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0009"
down_revision: str | None = "20250924_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TRANSACTION_TYPE_CHECK = (
    "transaction_type IN ('earn', 'redeem', 'adjustment', 'expire', 'refund')"
)

_AMOUNT_SIGN_CHECK = (
    "((transaction_type = 'redeem' AND amount_cents <= 0) OR "
    "(transaction_type = 'earn' AND amount_cents >= 0) OR "
    "transaction_type IN ('adjustment', 'expire', 'refund'))"
)


def upgrade() -> None:
    op.create_table(
        "bonus_transactions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("booking_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("balance_after_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _TRANSACTION_TYPE_CHECK,
            name="ck_bonus_transactions_transaction_type",
        ),
        sa.CheckConstraint(
            _AMOUNT_SIGN_CHECK,
            name="ck_bonus_transactions_amount_sign",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_bonus_transactions_customer_salon_id_customer_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_bonus_transactions_booking_salon_id_booking_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bonus_transactions_salon_id_customer_id_created_at",
        "bonus_transactions",
        ["salon_id", "customer_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_bonus_transactions_booking_id",
        "bonus_transactions",
        ["booking_id"],
        unique=False,
        postgresql_where=sa.text("booking_id IS NOT NULL"),
    )
    op.create_index(
        "uq_bonus_transactions_salon_id_idempotency_key",
        "bonus_transactions",
        ["salon_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_bonus_transactions_salon_id_idempotency_key",
        table_name="bonus_transactions",
    )
    op.drop_index(
        "ix_bonus_transactions_booking_id",
        table_name="bonus_transactions",
    )
    op.drop_index(
        "ix_bonus_transactions_salon_id_customer_id_created_at",
        table_name="bonus_transactions",
    )
    op.drop_table("bonus_transactions")
