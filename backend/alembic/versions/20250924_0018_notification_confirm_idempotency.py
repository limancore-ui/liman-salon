"""Unique confirm notification per booking (salon_id, booking_id, template_key)

Revision ID: 20250924_0018
Revises: 20250924_0017
Create Date: 2025-09-24

C13: idempotent booking_confirmed outbox row per tenant booking.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20250924_0018"
down_revision: str | None = "20250924_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_notifications_salon_id_booking_id_template_key",
        "notifications",
        ["salon_id", "booking_id", "template_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_notifications_salon_id_booking_id_template_key",
        "notifications",
        type_="unique",
    )
