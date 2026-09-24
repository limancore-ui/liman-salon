from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SalonScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon import Salon
    from app.db.models.user import User


class SalonUser(Base, UUIDPrimaryKeyMixin, SalonScopedMixin, TimestampMixin):
    """Membership and salon-scoped role for a platform user."""

    __tablename__ = "salon_users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    salon: Mapped[Salon] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="salon_memberships")

    __table_args__ = (
        UniqueConstraint("salon_id", "user_id", name="uq_salon_users_salon_id_user_id"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'staff', 'receptionist')",
            name="ck_salon_users_role",
        ),
        Index("ix_salon_users_user_id", "user_id"),
        Index("ix_salon_users_salon_id_role", "salon_id", "role"),
    )
