from __future__ import annotations

import uuid
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


@dataclass(frozen=True, slots=True)
class ServiceForAvailability:
    """Service fields used for Smart Gap slot sizing (includes inactive rows)."""

    id: uuid.UUID
    is_active: bool
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int


@dataclass(frozen=True, slots=True)
class ServiceAvailabilitySlot:
    """
    Bookable NET service window within one free gap.

    service_start: earliest net service start in the gap.
    service_end: latest net service end (finish time if started at latest valid start).
    """

    service_start: datetime
    service_end: datetime


@dataclass(frozen=True, slots=True)
class StaffServiceAvailability:
    staff_id: uuid.UUID
    slots: tuple[ServiceAvailabilitySlot, ...]


@dataclass(frozen=True, slots=True)
class ServiceAvailabilityResult:
    service_id: uuid.UUID
    staff: tuple[StaffServiceAvailability, ...]
