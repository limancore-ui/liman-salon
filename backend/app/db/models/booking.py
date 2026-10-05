from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    desc,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.db.models.customer import Customer
from app.db.models.staff import Staff
from app.db.models.service import Service

if TYPE_CHECKING:
    from app.db.models.salon import Salon
    from app.db.models.user import User
    from app.db.models.bonus_transaction import BonusTransaction
    from app.db.models.review import Review
    from app.db.models.notification import Notification
    from app.db.models.payment import Payment

_BOOKING_STATUS_CHECK = (
    "status IN ('pending', 'confirmed', 'in_progress', 'completed', "
    "'cancelled', 'no_show', 'expired')"
)

_EXCLUSION_WHERE = text("status IN ('pending', 'confirmed', 'in_progress')")


def _booking_bonus_transactions_join():
    from app.db.models.bonus_transaction import BonusTransaction

    return (
        (Booking.salon_id == BonusTransaction.salon_id)
        & (Booking.id == foreign(BonusTransaction.booking_id))
    )


def _booking_notifications_join():
    from app.db.models.notification import Notification

    return (
        (Booking.salon_id == Notification.salon_id)
        & (Booking.id == foreign(Notification.booking_id))
    )


def _booking_payments_join():
    from app.db.models.payment import Payment

    return (
        (Booking.salon_id == Payment.salon_id)
        & (Booking.id == foreign(Payment.booking_id))
    )


def _booking_review_join():
    from app.db.models.review import Review

    return (
        (Booking.salon_id == Review.salon_id)
        & (Booking.id == foreign(Review.booking_id))
    )


class Booking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Appointments: committed time on staff calendars (tenant-scoped)."""

    __tablename__ = "bookings"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    staff_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="admin",
    )
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    manage_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    salon: Mapped[Salon] = relationship(back_populates="bookings")
    customer: Mapped[Customer] = relationship(
        "Customer",
        back_populates="bookings",
        primaryjoin=lambda: (
            (Customer.salon_id == Booking.salon_id)
            & (Customer.id == foreign(Booking.customer_id))
        ),
    )
    staff: Mapped[Staff] = relationship(
        back_populates="bookings",
        primaryjoin=lambda: (
            (Staff.salon_id == Booking.salon_id)
            & (Staff.id == foreign(Booking.staff_id))
        ),
    )
    service: Mapped[Service] = relationship(
        back_populates="bookings",
        foreign_keys=[service_id],
        primaryjoin=lambda: (
            (Service.salon_id == Booking.salon_id)
            & (Service.id == foreign(Booking.service_id))
        ),
    )
    created_by_user: Mapped[User | None] = relationship(
        back_populates="bookings_created",
        foreign_keys=[created_by_user_id],
    )
    bonus_transactions: Mapped[list[BonusTransaction]] = relationship(
        back_populates="booking",
        primaryjoin=_booking_bonus_transactions_join,
    )
    review: Mapped[Review | None] = relationship(
        back_populates="booking",
        primaryjoin=_booking_review_join,
        uselist=False,
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="booking",
        primaryjoin=_booking_payments_join,
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="booking",
        primaryjoin=_booking_notifications_join,
    )

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_bookings_salon_id_id"),
        ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_bookings_customer_salon_id_customer_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="RESTRICT",
            name="fk_bookings_staff_salon_id_staff_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "service_id"],
            ["services.salon_id", "services.id"],
            ondelete="RESTRICT",
            name="fk_bookings_service_salon_id_service_id",
        ),
        CheckConstraint(
            "starts_at < ends_at",
            name="ck_bookings_starts_before_ends",
        ),
        CheckConstraint(
            "duration_minutes > 0",
            name="ck_bookings_duration_minutes",
        ),
        CheckConstraint(
            "price_cents >= 0",
            name="ck_bookings_price_cents",
        ),
        CheckConstraint(_BOOKING_STATUS_CHECK, name="ck_bookings_status"),
        Index(
            "ix_bookings_salon_id_staff_id_starts_at",
            "salon_id",
            "staff_id",
            "starts_at",
        ),
        Index(
            "ix_bookings_salon_id_customer_id_starts_at",
            "salon_id",
            "customer_id",
            desc("starts_at"),
        ),
        Index(
            "ix_bookings_salon_id_status_starts_at",
            "salon_id",
            "status",
            "starts_at",
        ),
        Index(
            "ix_bookings_salon_id_status_expires_at",
            "salon_id",
            "status",
            "expires_at",
            postgresql_where=text("status = 'pending' AND expires_at IS NOT NULL"),
        ),
        ExcludeConstraint(
            ("staff_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            name="excl_bookings_staff_time_overlap",
            using="gist",
            where=_EXCLUSION_WHERE,
        ),
    )
