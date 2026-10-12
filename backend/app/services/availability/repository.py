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
from app.services.schedule.types_impact import (
    ScheduleOverlay,
    WorkingHourUpdateOverlay,
    _UNSET,
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
        overlay: ScheduleOverlay | None = None,
    ) -> bool:
        if overlay is not None and (staff_id, service_id) in overlay.staff_service_detaches:
            return False
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
        overlay: ScheduleOverlay | None = None,
    ) -> tuple[list[WorkingHourSpec], list[WorkingHourSpec]]:
        stmt = select(WorkingHour).where(
            WorkingHour.salon_id == salon_id,
            or_(WorkingHour.staff_id.is_(None), WorkingHour.staff_id == staff_id),
        )
        rows = self._session.scalars(stmt).all()
        salon_defaults: list[WorkingHourSpec] = []
        staff_specific: list[WorkingHourSpec] = []
        updates_by_id: dict[uuid.UUID, WorkingHourUpdateOverlay] = {}
        if overlay is not None:
            updates_by_id = {u.working_hours_id: u for u in overlay.working_hours_updates}
        for row in rows:
            if overlay is not None and row.id in overlay.working_hours_deletes:
                continue
            spec = _working_hour_row_to_spec(row)
            if row.id in updates_by_id:
                spec = _apply_working_hour_update(row, updates_by_id[row.id])
            if spec.staff_id is None:
                salon_defaults.append(spec)
            elif spec.staff_id == staff_id:
                staff_specific.append(spec)
        if overlay is not None:
            for create in overlay.working_hours_creates:
                if create.staff_id is not None and create.staff_id != staff_id:
                    continue
                spec = create.to_spec()
                if spec.staff_id is None:
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
        overlay: ScheduleOverlay | None = None,
    ) -> list[BusyInterval]:
        stmt = select(BlockedPeriod).where(
            BlockedPeriod.salon_id == salon_id,
            or_(BlockedPeriod.staff_id.is_(None), BlockedPeriod.staff_id == staff_id),
            BlockedPeriod.starts_at < range_end_utc,
            BlockedPeriod.ends_at > range_start_utc,
        )
        rows = self._session.scalars(stmt).all()
        updates_by_id = {}
        if overlay is not None:
            updates_by_id = {u.blocked_period_id: u for u in overlay.blocked_period_updates}
        blocks: list[BusyInterval] = []
        for row in rows:
            if overlay is not None and row.id in overlay.blocked_period_deletes:
                continue
            starts_at = row.starts_at
            ends_at = row.ends_at
            block_staff_id = row.staff_id
            if row.id in updates_by_id:
                upd = updates_by_id[row.id]
                if upd.set_staff_id:
                    block_staff_id = upd.staff_id  # type: ignore[assignment]
                if upd.starts_at is not _UNSET and upd.starts_at is not None:
                    starts_at = upd.starts_at  # type: ignore[assignment]
                if upd.ends_at is not _UNSET and upd.ends_at is not None:
                    ends_at = upd.ends_at  # type: ignore[assignment]
            if block_staff_id is not None and block_staff_id != staff_id:
                continue
            if starts_at < range_end_utc and ends_at > range_start_utc:
                blocks.append(BusyInterval(start=starts_at, end=ends_at))
        if overlay is not None:
            for create in overlay.blocked_period_creates:
                if create.staff_id is not None and create.staff_id != staff_id:
                    continue
                interval = create.to_busy_interval()
                if interval.start < range_end_utc and interval.end > range_start_utc:
                    blocks.append(interval)
        return blocks

    def load_bookings_for_availability(
        self,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        range_start_utc: datetime,
        range_end_utc: datetime,
        as_of: datetime,
        exclude_booking_id: uuid.UUID | None = None,
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
        filters = [
            Booking.salon_id == salon_id,
            Booking.staff_id == staff_id,
            Booking.starts_at < range_end_utc,
            Booking.ends_at > range_start_utc,
            blocking_predicate,
        ]
        if exclude_booking_id is not None:
            filters.append(Booking.id != exclude_booking_id)
        stmt = select(Booking).where(*filters)
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


def _working_hour_row_to_spec(row: WorkingHour) -> WorkingHourSpec:
    return WorkingHourSpec(
        day_of_week=row.day_of_week,
        start_time=row.start_time,
        end_time=row.end_time,
        staff_id=row.staff_id,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
    )


def _apply_working_hour_update(
    row: WorkingHour, upd: WorkingHourUpdateOverlay
) -> WorkingHourSpec:
    staff_id = row.staff_id
    if upd.set_staff_id:
        staff_id = upd.staff_id  # type: ignore[assignment]
    day_of_week = (
        upd.day_of_week if upd.day_of_week is not _UNSET else row.day_of_week  # type: ignore[assignment]
    )
    start_time = (
        upd.start_time if upd.start_time is not _UNSET else row.start_time  # type: ignore[assignment]
    )
    end_time = (
        upd.end_time if upd.end_time is not _UNSET else row.end_time  # type: ignore[assignment]
    )
    effective_from = row.effective_from
    effective_to = row.effective_to
    if upd.set_effective_from:
        effective_from = upd.effective_from  # type: ignore[assignment]
    if upd.set_effective_to:
        effective_to = upd.effective_to  # type: ignore[assignment]
    return WorkingHourSpec(
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        staff_id=staff_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
