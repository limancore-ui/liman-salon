from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon import Salon
    from app.db.models.staff_service import StaffService
    from app.db.models.user import User
    from app.db.models.working_hour import WorkingHour


class Staff(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Bookable staff member within a salon. Optional link to users for app login."""

    __tablename__ = "staff"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    color_hex: Mapped[str | None] = mapped_column(CHAR(7), nullable=True)
    is_bookable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    salon: Mapped[Salon] = relationship(back_populates="staff")
    user: Mapped[User | None] = relationship(back_populates="staff_profiles")
    staff_services: Mapped[list[StaffService]] = relationship(back_populates="staff")
    working_hours: Mapped[list[WorkingHour]] = relationship(back_populates="staff")

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_staff_salon_id_id"),
        CheckConstraint(
            "color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$'",
            name="ck_staff_color_hex",
        ),
        Index(
            "uq_staff_salon_id_user_id",
            "salon_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index("ix_staff_salon_id_is_active_is_bookable", "salon_id", "is_active", "is_bookable"),
        Index(
            "ix_staff_user_id",
            "user_id",
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )
