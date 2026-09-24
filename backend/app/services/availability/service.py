from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.services.availability.booking_block import booking_to_busy_interval
from app.services.availability.intervals import (
    build_working_intervals_for_range,
    clip_intervals_to_range,
    filter_gaps_min_duration,
    salon_local_date_range_to_utc_bounds,
    subtract_busy_from_working,
)
from app.services.availability.repository import AvailabilityRepository
from app.services.availability.types import TimeInterval


class AvailabilityService:
    """Compute free bookable gaps for one staff member within a salon."""

    def __init__(self, session: Session) -> None:
        self._repo = AvailabilityRepository(session)

    def get_free_gaps(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        start_date: date,
        end_date: date,
        service_duration_minutes: int,
        as_of: datetime,
    ) -> list[TimeInterval]:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware (UTC recommended)")
        if end_date < start_date:
            return []
        if service_duration_minutes <= 0:
            raise ValueError("service_duration_minutes must be positive")

        if not self._repo.staff_belongs_to_salon(salon_id, staff_id):
            return []

        tz_name = self._repo.get_salon_timezone(salon_id)
        if not tz_name:
            return []
        tz = ZoneInfo(tz_name)

        range_start_utc, range_end_utc = salon_local_date_range_to_utc_bounds(
            start_date, end_date, tz
        )

        salon_defaults, staff_specific = self._repo.load_working_hours(salon_id, staff_id)
        working = build_working_intervals_for_range(
            start_date, end_date, salon_defaults, staff_specific, tz
        )
        working = clip_intervals_to_range(working, range_start_utc, range_end_utc)

        blocks = self._repo.load_blocked_periods(
            salon_id, staff_id, range_start_utc, range_end_utc
        )
        bookings = self._repo.load_bookings_for_availability(
            salon_id, staff_id, range_start_utc, range_end_utc, as_of
        )
        busy_from_bookings = [
            b
            for occ in bookings
            if (b := booking_to_busy_interval(occ, as_of)) is not None
        ]

        free = subtract_busy_from_working(working, [*blocks, *busy_from_bookings])
        return filter_gaps_min_duration(free, service_duration_minutes)
