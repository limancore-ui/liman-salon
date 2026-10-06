from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.salon import Salon
    from app.db.models.user import User

_EVENT_TYPE_CHECK = "event_type IN ('public_booking_pending')"


def _admin_notification_booking_join():
    from app.db.models.booking import Booking

    return (
        (Booking.salon_id == AdminNotificationEvent.salon_id)
        & (Booking.id == foreign(AdminNotificationEvent.booking_id))
    )


class AdminNotificationEvent(Base, UUIDPrimaryKeyMixin):
    """In-app admin panel notification (not external provider outbox)."""

    __tablename__ = "admin_notification_events"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(back_populates="admin_notification_events")
    booking: Mapped[Booking] = relationship(
        back_populates="admin_notification_events",
        primaryjoin=_admin_notification_booking_join,
    )
    recipient: Mapped[User] = relationship(
        back_populates="admin_notification_events",
    )

    __table_args__ = (
        UniqueConstraint(
            "salon_id",
            "booking_id",
            "recipient_user_id",
            "event_type",
            name="uq_admin_notification_events_recipient_booking",
        ),
        ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="CASCADE",
            name="fk_admin_notification_events_booking",
        ),
        CheckConstraint(_EVENT_TYPE_CHECK, name="ck_admin_notification_events_event_type"),
        Index(
            "ix_admin_notification_events_recipient_created",
            "salon_id",
            "recipient_user_id",
            desc("created_at"),
        ),
        Index(
            "ix_admin_notification_events_salon_booking",
            "salon_id",
            "booking_id",
        ),
    )
