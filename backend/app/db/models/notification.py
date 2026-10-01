from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.customer import Customer
    from app.db.models.salon import Salon

_NOTIFICATION_STATUS_CHECK = (
    "status IN ('pending', 'sent', 'failed', 'skipped')"
)


class Notification(Base, UUIDPrimaryKeyMixin):
    """Outbox / delivery log for notification provider abstraction."""

    __tablename__ = "notifications"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(320), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default="0",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(back_populates="notifications")
    booking: Mapped[Booking | None] = relationship(
        back_populates="notifications",
        foreign_keys=[salon_id, booking_id],
    )
    customer: Mapped[Customer | None] = relationship(
        back_populates="notifications",
        foreign_keys=[salon_id, customer_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "salon_id",
            "booking_id",
            "template_key",
            name="uq_notifications_salon_id_booking_id_template_key",
        ),
        ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_notifications_booking_salon_id_booking_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="SET NULL",
            name="fk_notifications_customer_salon_id_customer_id",
        ),
        CheckConstraint(_NOTIFICATION_STATUS_CHECK, name="ck_notifications_status"),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_notifications_attempt_count",
        ),
        Index(
            "ix_notifications_salon_id_status_scheduled_for",
            "salon_id",
            "status",
            "scheduled_for",
        ),
        Index(
            "ix_notifications_salon_id_booking_id",
            "salon_id",
            "booking_id",
        ),
        Index(
            "ix_notifications_created_at",
            desc("created_at"),
        ),
    )
