from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass(frozen=True, slots=True)
class TimeInterval:
    """Half-open UTC interval [start, end)."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("TimeInterval bounds must be timezone-aware")
        if self.start >= self.end:
            raise ValueError("TimeInterval start must be before end")


@dataclass(frozen=True, slots=True)
class WorkingHourSpec:
    """Recurring weekly window (local time-of-day) with optional effective range."""

    day_of_week: int
    start_time: time
    end_time: time
    staff_id: object | None
    effective_from: date | None
    effective_to: date | None


@dataclass(frozen=True, slots=True)
class BusyInterval:
    """Blocked time or booking occupancy in UTC."""

    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class BookingOccupancy:
    """Booking row fields needed for availability blocking."""

    starts_at: datetime
    ends_at: datetime
    status: str
    expires_at: datetime | None
