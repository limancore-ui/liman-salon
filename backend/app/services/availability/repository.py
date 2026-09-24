from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models.blocked_period import BlockedPeriod
from app.db.models.booking import Booking
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.services.availability.types import (
    BookingOccupancy,
    BusyInterval,
    ServiceForAvailability,
    WorkingHourSpec,
)


class AvailabilityRepository:
    """Tenant-scoped reads for availability (always filtered by salon_id)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_salon_timezone(self, salon_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(Salon.timezone).where(Salon.id == salon_id)
        )

    def get_service_for_availability(
        self, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> ServiceForAvailability | None:
        """Tenant-scoped service row (active or inactive)."""
        row = self._session.scalar(
            select(Service).where(
                Service.salon_id == salon_id,
                Service.id == service_id,
            )
        )
        if row is None:
            return None
        return ServiceForAvailability(
            id=row.id,
            is_active=row.is_active,
            duration_minutes=row.duration_minutes,
            buffer_before_minutes=row.buffer_before_minutes,
            buffer_after_minutes=row.buffer_after_minutes,
        )

    def get_active_service_for_availability(
        self, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> ServiceForAvailability | None:
        service = self.get_service_for_availability(salon_id, service_id)
        if service is None or not service.is_active:
            return None
        return service

    def list_bookable_staff_for_service(
        self, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> list[uuid.UUID]:
        stmt = (
            select(Staff.id)
            .join(
                StaffService,
                (StaffService.staff_id == Staff.id)
                & (StaffService.salon_id == Staff.salon_id),
            )
            .where(
                StaffService.salon_id == salon_id,
                StaffService.service_id == service_id,
                Staff.salon_id == salon_id,
                Staff.is_active.is_(True),
                Staff.is_bookable.is_(True),
            )
            .order_by(Staff.sort_order, Staff.display_name, Staff.id)
        )
        return list(self._session.scalars(stmt).all())

    def staff_eligible_for_service(
        self,
        salon_id: uuid.UUID,
        service_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> bool:
        found = self._session.scalar(
            select(Staff.id)
            .join(
                StaffService,
                (StaffService.staff_id == Staff.id)
                & (StaffService.salon_id == Staff.salon_id),
            )
            .where(
                StaffService.salon_id == salon_id,
                StaffService.service_id == service_id,
                StaffService.staff_id == staff_id,
                Staff.salon_id == salon_id,
                Staff.id == staff_id,
                Staff.is_active.is_(True),
                Staff.is_bookable.is_(True),
            )
        )
        return found is not None

    def staff_belongs_to_salon(self, salon_id: uuid.UUID, staff_id: uuid.UUID) -> bool:
        found = self._session.scalar(
            select(Staff.id).where(
                Staff.salon_id == salon_id,
                Staff.id == staff_id,
            )
        )
        return found is not None

    def load_working_hours(
        self,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
    ) -> tuple[list[WorkingHourSpec], list[WorkingHourSpec]]:
        stmt = select(WorkingHour).where(
            WorkingHour.salon_id == salon_id,
            or_(WorkingHour.staff_id.is_(None), WorkingHour.staff_id == staff_id),
        )
        rows = self._session.scalars(stmt).all()
        salon_defaults: list[WorkingHourSpec] = []
        staff_specific: list[WorkingHourSpec] = []
        for row in rows:
            spec = WorkingHourSpec(
                day_of_week=row.day_of_week,
                start_time=row.start_time,
                end_time=row.end_time,
                staff_id=row.staff_id,
                effective_from=row.effective_from,
                effective_to=row.effective_to,
            )
            if row.staff_id is None:
                salon_defaults.append(spec)
            else:
                staff_specific.append(spec)
        return salon_defaults, staff_specific

    def load_blocked_periods(
        self,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        range_start_utc: datetime,
        range_end_utc: datetime,
    ) -> list[BusyInterval]:
        stmt = select(BlockedPeriod).where(
            BlockedPeriod.salon_id == salon_id,
            or_(BlockedPeriod.staff_id.is_(None), BlockedPeriod.staff_id == staff_id),
            BlockedPeriod.starts_at < range_end_utc,
            BlockedPeriod.ends_at > range_start_utc,
        )
        rows = self._session.scalars(stmt).all()
        return [BusyInterval(start=r.starts_at, end=r.ends_at) for r in rows]

    def load_bookings_for_availability(
        self,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        range_start_utc: datetime,
        range_end_utc: datetime,
        as_of: datetime,
    ) -> list[BookingOccupancy]:
        """Load bookings that may overlap the range; blocking filter uses explicit as_of."""
        blocking_predicate = or_(
            Booking.status.in_(("confirmed", "in_progress")),
            and_(
                Booking.status == "pending",
                Booking.expires_at.isnot(None),
                Booking.expires_at > as_of,
            ),
        )
        stmt = select(Booking).where(
            Booking.salon_id == salon_id,
            Booking.staff_id == staff_id,
            Booking.starts_at < range_end_utc,
            Booking.ends_at > range_start_utc,
            blocking_predicate,
        )
        rows = self._session.scalars(stmt).all()
        return [
            BookingOccupancy(
                starts_at=r.starts_at,
                ends_at=r.ends_at,
                status=r.status,
                expires_at=r.expires_at,
            )
            for r in rows
        ]
