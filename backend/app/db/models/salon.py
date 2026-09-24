from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon_user import SalonUser
    from app.db.models.service import Service
    from app.db.models.staff import Staff
    from app.db.models.staff_service import StaffService
    from app.db.models.blocked_period import BlockedPeriod
    from app.db.models.booking import Booking
    from app.db.models.customer import Customer
    from app.db.models.working_hour import WorkingHour
    from app.db.models.bonus_transaction import BonusTransaction


class Salon(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tenant root (salon). No salon_id on self."""

    __tablename__ = "salons"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en")
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    memberships: Mapped[list[SalonUser]] = relationship(
        back_populates="salon",
        cascade="all, delete-orphan",
    )
    staff: Mapped[list[Staff]] = relationship(back_populates="salon")
    services: Mapped[list[Service]] = relationship(back_populates="salon")
    staff_services: Mapped[list[StaffService]] = relationship(back_populates="salon")
    working_hours: Mapped[list[WorkingHour]] = relationship(back_populates="salon")
    blocked_periods: Mapped[list[BlockedPeriod]] = relationship(back_populates="salon")
    customers: Mapped[list[Customer]] = relationship(back_populates="salon")
    bookings: Mapped[list[Booking]] = relationship(back_populates="salon")
    bonus_transactions: Mapped[list[BonusTransaction]] = relationship(
        back_populates="salon",
    )

    __table_args__ = (
        CheckConstraint("char_length(slug) >= 2", name="ck_salons_slug_min_length"),
        Index("ix_salons_is_active", "is_active"),
    )
