from __future__ import annotations

from datetime import datetime, timezone

from app.services.availability.intervals import net_service_slots_from_free_gaps
from app.services.availability.types import TimeInterval

UTC = timezone.utc


def test_gap_too_short_for_buffers_and_duration() -> None:
    gaps = [
        TimeInterval(
            start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
            end=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
        )
    ]
    assert (
        net_service_slots_from_free_gaps(
            gaps,
            duration_minutes=60,
            buffer_before_minutes=15,
            buffer_after_minutes=15,
        )
        == []
    )
