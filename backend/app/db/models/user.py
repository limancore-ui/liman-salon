from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon_user import SalonUser
    from app.db.models.blocked_period import BlockedPeriod
    from app.db.models.booking import Booking
    from app.db.models.customer import Customer
    from app.db.models.staff import Staff
    from app.db.models.bonus_transaction import BonusTransaction


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Platform identity (login). Not tenant-scoped."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    salon_memberships: Mapped[list[SalonUser]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    staff_profiles: Mapped[list[Staff]] = relationship(back_populates="user")
    blocked_periods_created: Mapped[list[BlockedPeriod]] = relationship(
        back_populates="created_by_user",
    )
    customers: Mapped[list[Customer]] = relationship(back_populates="user")
    bookings_created: Mapped[list[Booking]] = relationship(
        back_populates="created_by_user",
    )
    bonus_transactions_created: Mapped[list[BonusTransaction]] = relationship(
        back_populates="created_by_user",
    )

    __table_args__ = (
        Index("ix_users_email_lower", func.lower(email), unique=True),
        Index("ix_users_is_active", "is_active"),
    )
