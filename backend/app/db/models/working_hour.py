from __future__ import annotations

import uuid
from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    Time,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon import Salon
    from app.db.models.staff import Staff


def _working_hour_staff_join():
    from app.db.models.staff import Staff

    return (
        (Staff.salon_id == WorkingHour.salon_id)
        & (Staff.id == foreign(WorkingHour.staff_id))
    )


class WorkingHour(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Recurring weekly availability for salon default and/or specific staff."""

    __tablename__ = "working_hours"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    salon: Mapped[Salon] = relationship(back_populates="working_hours")
    staff: Mapped[Staff | None] = relationship(
        back_populates="working_hours",
        primaryjoin=_working_hour_staff_join,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="CASCADE",
            name="fk_working_hours_staff_salon_id_staff_id",
        ),
        CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name="ck_working_hours_day_of_week",
        ),
        CheckConstraint(
            "start_time < end_time",
            name="ck_working_hours_start_before_end",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_from <= effective_to",
            name="ck_working_hours_effective_range",
        ),
        Index(
            "ix_working_hours_salon_id_staff_id_day_of_week",
            "salon_id",
            "staff_id",
            "day_of_week",
        ),
        Index(
            "ix_working_hours_salon_id_day_of_week",
            "salon_id",
            "day_of_week",
            postgresql_where=text("staff_id IS NULL"),
        ),
    )
