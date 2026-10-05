from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.salon import Salon
    from app.db.models.service import Service
    from app.db.models.staff import Staff


def _staff_service_staff_join():
    from app.db.models.staff import Staff

    return (
        (Staff.salon_id == StaffService.salon_id)
        & (Staff.id == foreign(StaffService.staff_id))
    )


def _staff_service_service_join():
    from app.db.models.service import Service

    return (
        (Service.salon_id == StaffService.salon_id)
        & (Service.id == foreign(StaffService.service_id))
    )


class StaffService(Base, UUIDPrimaryKeyMixin):
    """Junction: which staff can perform which services (tenant-scoped)."""

    __tablename__ = "staff_services"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(back_populates="staff_services")
    staff: Mapped[Staff] = relationship(
        back_populates="staff_services",
        foreign_keys=[staff_id],
        primaryjoin=_staff_service_staff_join,
    )
    service: Mapped[Service] = relationship(
        back_populates="staff_services",
        foreign_keys=[service_id],
        primaryjoin=_staff_service_service_join,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="CASCADE",
            name="fk_staff_services_staff_salon_id_staff_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "service_id"],
            ["services.salon_id", "services.id"],
            ondelete="CASCADE",
            name="fk_staff_services_service_salon_id_service_id",
        ),
        UniqueConstraint("staff_id", "service_id", name="uq_staff_services_staff_id_service_id"),
        UniqueConstraint(
            "salon_id",
            "staff_id",
            "service_id",
            name="uq_staff_services_salon_id_staff_id_service_id",
        ),
        Index("ix_staff_services_salon_id_service_id", "salon_id", "service_id"),
        Index("ix_staff_services_salon_id_staff_id", "salon_id", "staff_id"),
    )
