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
    Uuid,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon import Salon
    from app.db.models.staff import Staff
    from app.db.models.user import User


def _blocked_period_staff_join():
    from app.db.models.staff import Staff

    return (
        (Staff.salon_id == BlockedPeriod.salon_id)
        & (Staff.id == foreign(BlockedPeriod.staff_id))
    )


class BlockedPeriod(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Time off, holidays, and manual blocks (salon-wide or staff-specific)."""

    __tablename__ = "blocked_periods"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    block_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="manual",
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    salon: Mapped[Salon] = relationship(back_populates="blocked_periods")
    staff: Mapped[Staff | None] = relationship(
        back_populates="blocked_periods",
        primaryjoin=_blocked_period_staff_join,
    )
    created_by_user: Mapped[User | None] = relationship(
        back_populates="blocked_periods_created",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="CASCADE",
            name="fk_blocked_periods_staff_salon_id_staff_id",
        ),
        CheckConstraint(
            "starts_at < ends_at",
            name="ck_blocked_periods_starts_before_ends",
        ),
        CheckConstraint(
            "block_type IN ('manual', 'holiday', 'time_off')",
            name="ck_blocked_periods_block_type",
        ),
        Index(
            "ix_blocked_periods_salon_id_staff_id_starts_at_ends_at",
            "salon_id",
            "staff_id",
            "starts_at",
            "ends_at",
        ),
        Index(
            "ix_blocked_periods_salon_id_starts_at",
            "salon_id",
            "starts_at",
        ),
    )
