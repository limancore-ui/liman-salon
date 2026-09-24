from __future__ import annotations

from datetime import datetime, timezone

from app.services.availability.booking_block import (
    booking_blocks_availability,
    booking_to_busy_interval,
)
from app.services.availability.types import BookingOccupancy

UTC = timezone.utc
AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


def _booking(**kwargs: object) -> BookingOccupancy:
    defaults = {
        "starts_at": datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
        "ends_at": datetime(2025, 6, 1, 11, 0, tzinfo=UTC),
        "status": "confirmed",
        "expires_at": None,
    }
    defaults.update(kwargs)
    return BookingOccupancy(**defaults)  # type: ignore[arg-type]


def test_confirmed_booking_blocks() -> None:
    assert booking_blocks_availability(_booking(status="confirmed"), AS_OF)


def test_in_progress_booking_blocks() -> None:
    assert booking_blocks_availability(_booking(status="in_progress"), AS_OF)


def test_cancelled_booking_does_not_block() -> None:
    assert not booking_blocks_availability(_booking(status="cancelled"), AS_OF)


def test_expired_pending_does_not_block() -> None:
    b = _booking(
        status="pending",
        expires_at=datetime(2025, 6, 1, 11, 0, tzinfo=UTC),
    )
    assert not booking_blocks_availability(b, AS_OF)


def test_active_pending_blocks() -> None:
    b = _booking(
        status="pending",
        expires_at=datetime(2025, 6, 1, 13, 0, tzinfo=UTC),
    )
    assert booking_blocks_availability(b, AS_OF)


def test_pending_without_expires_at_does_not_block() -> None:
    b = _booking(status="pending", expires_at=None)
    assert not booking_blocks_availability(b, AS_OF)


def test_booking_to_busy_interval_returns_none_when_not_blocking() -> None:
    assert booking_to_busy_interval(_booking(status="cancelled"), AS_OF) is None
