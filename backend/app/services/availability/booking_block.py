from __future__ import annotations

from datetime import datetime

from app.services.availability.types import BookingOccupancy, BusyInterval

_BLOCKING_STATUSES = frozenset({"confirmed", "in_progress", "pending"})


def booking_blocks_availability(booking: BookingOccupancy, as_of: datetime) -> bool:
    """Whether a booking subtracts from workable time at evaluation time `as_of`."""
    if booking.status not in _BLOCKING_STATUSES:
        return False
    if booking.status in ("confirmed", "in_progress"):
        return True
    # pending
    if booking.expires_at is None:
        return False
    if as_of.tzinfo is None or booking.expires_at.tzinfo is None:
        raise ValueError("as_of and expires_at must be timezone-aware")
    return booking.expires_at > as_of


def booking_to_busy_interval(booking: BookingOccupancy, as_of: datetime) -> BusyInterval | None:
    if not booking_blocks_availability(booking, as_of):
        return None
    return BusyInterval(start=booking.starts_at, end=booking.ends_at)
