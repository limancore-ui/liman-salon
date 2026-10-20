"""Allow admin notification events for confirmed public bookings.

Revision ID: 20261018_0022
Revises: 20261018_0021
Create Date: 2026-10-18

Downgrade refuses to proceed while confirmed-booking notification events
exist, preserving notification history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0022"
down_revision: str | None = "20261018_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_admin_notification_events_event_type",
        "admin_notification_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_admin_notification_events_event_type",
        "admin_notification_events",
        "event_type IN ('public_booking_pending', 'public_booking_confirmed')",
    )


def downgrade() -> None:
    connection = op.get_bind()

    confirmed_events_exist = connection.scalar(
        sa.text(
            "SELECT EXISTS ("
            "SELECT 1 FROM admin_notification_events "
            "WHERE event_type = 'public_booking_confirmed'"
            ")"
        )
    )

    if confirmed_events_exist:
        raise RuntimeError(
            "Cannot downgrade migration 20261018_0022: confirmed-booking "
            "notification events exist. Notification history was preserved; "
            "resolve the compatibility issue before retrying the downgrade."
        )

    op.drop_constraint(
        "ck_admin_notification_events_event_type",
        "admin_notification_events",
        type_="check",
    )
    op.create_check_constraint(
        "ck_admin_notification_events_event_type",
        "admin_notification_events",
        "event_type IN ('public_booking_pending')",
    )
