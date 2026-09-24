"""notifications table

Revision ID: 20250924_0013
Revises: 20250924_0012
Create Date: 2025-09-24

Notification outbox / delivery log (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250924_0013"
down_revision: str | None = "20250924_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOTIFICATION_STATUS_CHECK = (
    "status IN ('pending', 'sent', 'failed', 'skipped')"
)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("booking_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("template_key", sa.String(length=64), nullable=False),
        sa.Column("recipient_address", sa.String(length=320), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column(
            "attempt_count",
            sa.SmallInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_NOTIFICATION_STATUS_CHECK, name="ck_notifications_status"),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_notifications_attempt_count",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_notifications_booking_salon_id_booking_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="SET NULL",
            name="fk_notifications_customer_salon_id_customer_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_salon_id_status_scheduled_for",
        "notifications",
        ["salon_id", "status", "scheduled_for"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_salon_id_booking_id",
        "notifications",
        ["salon_id", "booking_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        [sa.text("created_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_salon_id_booking_id", table_name="notifications")
    op.drop_index(
        "ix_notifications_salon_id_status_scheduled_for",
        table_name="notifications",
    )
    op.drop_table("notifications")
