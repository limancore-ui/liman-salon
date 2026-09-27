from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ServiceSnapshot:
    """Service fields copied onto a booking at creation time."""

    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price_cents: int
    currency_code: str


@dataclass(frozen=True, slots=True)
class OccupiedInterval:
    """
    Persisted booking calendar occupancy (stored in bookings.starts_at / ends_at).

    Buffer convention (MVP booking service):
    - requested_service_start: NET service start (customer-facing service time).
    - occupied_start = requested_service_start - buffer_before_minutes
    - occupied_end = requested_service_start + duration_minutes + buffer_after_minutes
    """

    net_service_start: datetime
    occupied_start: datetime
    occupied_end: datetime
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int

    @property
    def occupied_span_minutes(self) -> int:
        delta = self.occupied_end - self.occupied_start
        return int(delta.total_seconds() // 60)


def compute_occupied_interval(
    *,
    requested_service_start: datetime,
    duration_minutes: int,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
) -> OccupiedInterval:
    """Derive occupied bounds from NET service start and service buffer/duration."""
    if requested_service_start.tzinfo is None:
        raise ValueError("requested_service_start must be timezone-aware")
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if buffer_before_minutes < 0 or buffer_after_minutes < 0:
        raise ValueError("buffer minutes must be non-negative")

    occupied_start = requested_service_start - timedelta(minutes=buffer_before_minutes)
    occupied_end = requested_service_start + timedelta(
        minutes=duration_minutes + buffer_after_minutes
    )
    if occupied_start >= occupied_end:
        raise ValueError("occupied interval must be non-empty")

    return OccupiedInterval(
        net_service_start=requested_service_start,
        occupied_start=occupied_start,
        occupied_end=occupied_end,
        duration_minutes=duration_minutes,
        buffer_before_minutes=buffer_before_minutes,
        buffer_after_minutes=buffer_after_minutes,
    )


@dataclass(frozen=True, slots=True)
class CreateBookingResult:
    booking_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str


@dataclass(frozen=True, slots=True)
class BookingListRow:
    """Admin list view row with joined display names (tenant-scoped)."""

    id: UUID
    status: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    price_cents: int
    customer_name: str
    customer_phone: str | None
    staff_name: str
    service_name: str
    source: str
    created_at: datetime
