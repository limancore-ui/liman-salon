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
    SmallInteger,
    String,
    Text,
    Uuid,
    desc,
    text,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.customer import Customer
    from app.db.models.salon import Salon
    from app.db.models.staff import Staff
    from app.db.models.user import User

_REVIEW_STATUS_CHECK = (
    "status IN ('pending', 'published', 'rejected', 'hidden')"
)


def _review_booking_join():
    from app.db.models.booking import Booking

    return (
        (Booking.salon_id == Review.salon_id)
        & (Booking.id == foreign(Review.booking_id))
    )


def _review_customer_join():
    from app.db.models.customer import Customer

    return (
        (Customer.salon_id == Review.salon_id)
        & (Customer.id == foreign(Review.customer_id))
    )


def _review_staff_join():
    from app.db.models.staff import Staff

    return (
        (Staff.salon_id == Review.salon_id)
        & (Staff.id == foreign(Review.staff_id))
    )


class Review(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Post-visit feedback with moderation (tenant-scoped)."""

    __tablename__ = "reviews"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    staff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    moderated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    moderated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    salon: Mapped[Salon] = relationship(back_populates="reviews")
    booking: Mapped[Booking | None] = relationship(
        back_populates="review",
        primaryjoin=_review_booking_join,
    )
    customer: Mapped[Customer] = relationship(
        back_populates="reviews",
        primaryjoin=_review_customer_join,
    )
    staff: Mapped[Staff | None] = relationship(
        back_populates="reviews",
        primaryjoin=_review_staff_join,
    )
    moderated_by_user: Mapped[User | None] = relationship(
        back_populates="reviews_moderated",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_reviews_booking_salon_id_booking_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_reviews_customer_salon_id_customer_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="SET NULL",
            name="fk_reviews_staff_salon_id_staff_id",
        ),
        CheckConstraint(
            "rating BETWEEN 1 AND 5",
            name="ck_reviews_rating",
        ),
        CheckConstraint(
            _REVIEW_STATUS_CHECK,
            name="ck_reviews_status",
        ),
        Index(
            "ix_reviews_salon_id_status_created_at",
            "salon_id",
            "status",
            desc("created_at"),
        ),
        Index(
            "ix_reviews_salon_id_staff_id_status",
            "salon_id",
            "staff_id",
            "status",
            postgresql_where=text("status = 'published'"),
        ),
        Index(
            "uq_reviews_booking_id",
            "booking_id",
            unique=True,
            postgresql_where=text("booking_id IS NOT NULL"),
        ),
    )
