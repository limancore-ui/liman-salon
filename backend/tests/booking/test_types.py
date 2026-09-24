from __future__ import annotations

from datetime import datetime, timezone

from app.services.booking.types import compute_occupied_interval

UTC = timezone.utc


def test_buffer_convention_occupied_bounds_persisted_on_booking_row() -> None:
    """
    requested_service_start is NET service start; starts_at/ends_at store occupied span.
    """
    requested = datetime(2025, 6, 2, 10, 0, tzinfo=UTC)
    occ = compute_occupied_interval(
        requested_service_start=requested,
        duration_minutes=60,
        buffer_before_minutes=15,
        buffer_after_minutes=10,
    )
    assert occ.net_service_start == requested
    assert occ.occupied_start == datetime(2025, 6, 2, 9, 45, tzinfo=UTC)
    assert occ.occupied_end == datetime(2025, 6, 2, 11, 10, tzinfo=UTC)
    assert occ.occupied_span_minutes == 85
