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

    def is_occupied_interval_available(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        occupied_start: datetime,
        occupied_end: datetime,
        as_of: datetime,
    ) -> bool:
        """
        True when [occupied_start, occupied_end) lies entirely inside one free gap.

        Uses the same schedule/booking rules as get_free_gaps; minimum gap length is
        the occupied span in minutes (buffers included when stored in starts_at/ends_at).
        """
        if occupied_start.tzinfo is None or occupied_end.tzinfo is None:
            raise ValueError("occupied bounds must be timezone-aware")
        if occupied_start >= occupied_end:
            return False

        span_minutes = int((occupied_end - occupied_start).total_seconds() // 60)
        if span_minutes <= 0:
            return False

        tz_name = self._repo.get_salon_timezone(salon_id)
        if not tz_name:
            return False
        tz = ZoneInfo(tz_name)
        start_date = occupied_start.astimezone(tz).date()
        end_date = occupied_end.astimezone(tz).date()
        gaps = self.get_free_gaps(
            salon_id=salon_id,
            staff_id=staff_id,
            start_date=start_date,
            end_date=end_date,
            service_duration_minutes=span_minutes,
            as_of=as_of,
        )
        for gap in gaps:
            if gap.start <= occupied_start and gap.end >= occupied_end:
                return True
        return False
