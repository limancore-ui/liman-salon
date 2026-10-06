"""admin_notification_events for in-app admin panel alerts

Revision ID: 20250924_0019
Revises: 20250924_0018
Create Date: 2025-09-24

Internal admin notifications for public booking holds (not WhatsApp outbox).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20250924_0019"
down_revision: str | None = "20250924_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_notification_events",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('public_booking_pending')",
            name="ck_admin_notification_events_event_type",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="CASCADE",
            name="fk_admin_notification_events_booking",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "salon_id",
            "booking_id",
            "recipient_user_id",
            "event_type",
            name="uq_admin_notification_events_recipient_booking",
        ),
    )
    op.create_index(
        "ix_admin_notification_events_recipient_created",
        "admin_notification_events",
        ["salon_id", "recipient_user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_notification_events_salon_booking",
        "admin_notification_events",
        ["salon_id", "booking_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_notification_events_salon_booking",
        table_name="admin_notification_events",
    )
    op.drop_index(
        "ix_admin_notification_events_recipient_created",
        table_name="admin_notification_events",
    )
    op.drop_table("admin_notification_events")
