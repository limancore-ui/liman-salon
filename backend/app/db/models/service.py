from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.salon import Salon
    from app.db.models.staff_service import StaffService


def _service_staff_services_join():
    from app.db.models.staff_service import StaffService

    return (
        (Service.salon_id == StaffService.salon_id)
        & (Service.id == foreign(StaffService.service_id))
    )


def _service_bookings_join():
    from app.db.models.booking import Booking

    return (
        (Service.salon_id == Booking.salon_id)
        & (Service.id == foreign(Booking.service_id))
    )


class Service(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Salon service catalog (bookable offerings)."""

    __tablename__ = "services"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_before_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    buffer_after_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    salon: Mapped[Salon] = relationship(back_populates="services")
    staff_services: Mapped[list[StaffService]] = relationship(
        back_populates="service",
        primaryjoin=_service_staff_services_join,
    )
    bookings: Mapped[list[Booking]] = relationship(
        "Booking",
        back_populates="service",
        primaryjoin=_service_bookings_join,
    )

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_services_salon_id_id"),
        CheckConstraint("duration_minutes > 0", name="ck_services_duration_minutes"),
        CheckConstraint(
            "buffer_before_minutes >= 0 AND buffer_after_minutes >= 0",
            name="ck_services_buffer_minutes",
        ),
        CheckConstraint("price_cents >= 0", name="ck_services_price_cents"),
        Index("ix_services_salon_id_is_active_sort_order", "salon_id", "is_active", "sort_order"),
    )
