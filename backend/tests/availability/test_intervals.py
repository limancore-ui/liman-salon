from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from app.services.availability.intervals import (
    build_working_intervals_for_day,
    filter_gaps_min_duration,
    merge_intervals,
    subtract_busy_from_working,
)
from app.services.availability.types import BusyInterval, TimeInterval, WorkingHourSpec

UTC = timezone.utc


def _utc(h: int, m: int = 0) -> datetime:
    return datetime(2025, 6, 2, h, m, tzinfo=UTC)


def test_merge_overlapping_intervals() -> None:
    merged = merge_intervals(
        [
            TimeInterval(start=_utc(9), end=_utc(12)),
            TimeInterval(start=_utc(11), end=_utc(14)),
        ]
    )
    assert merged == [TimeInterval(start=_utc(9), end=_utc(14))]


def test_subtract_booking_leaves_gaps_before_and_after() -> None:
    working = [TimeInterval(start=_utc(9), end=_utc(17))]
    busy = [BusyInterval(start=_utc(11), end=_utc(13))]
    free = subtract_busy_from_working(working, busy)
    assert free == [
        TimeInterval(start=_utc(9), end=_utc(11)),
        TimeInterval(start=_utc(13), end=_utc(17)),
    ]


def test_subtract_overlapping_busy_merged_first() -> None:
    working = [TimeInterval(start=_utc(9), end=_utc(18))]
    busy = [
        BusyInterval(start=_utc(10), end=_utc(11)),
        BusyInterval(start=_utc(10, 30), end=_utc(12)),
    ]
    free = subtract_busy_from_working(working, busy)
    assert free == [
        TimeInterval(start=_utc(9), end=_utc(10)),
        TimeInterval(start=_utc(12), end=_utc(18)),
    ]


def test_no_working_hours_yields_empty() -> None:
    tz = ZoneInfo("UTC")
    assert (
        build_working_intervals_for_day(date(2025, 6, 2), [], [], tz) == []
    )


def test_staff_hours_override_salon_default() -> None:
    tz = ZoneInfo("UTC")
    local = date(2025, 6, 2)  # Monday
    salon = [
        WorkingHourSpec(
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            staff_id=None,
            effective_from=None,
            effective_to=None,
        )
    ]
    staff = [
        WorkingHourSpec(
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(14, 0),
            staff_id="staff",
            effective_from=None,
            effective_to=None,
        )
    ]
    intervals = build_working_intervals_for_day(local, salon, staff, tz)
    assert intervals == [TimeInterval(start=_utc(10), end=_utc(14))]


def test_working_hours_timezone_conversion() -> None:
    tz = ZoneInfo("Asia/Almaty")  # UTC+5 in June
    local = date(2025, 6, 2)
    rows = [
        WorkingHourSpec(
            day_of_week=local.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            staff_id=None,
            effective_from=None,
            effective_to=None,
        )
    ]
    intervals = build_working_intervals_for_day(local, rows, [], tz)
    assert len(intervals) == 1
    assert intervals[0].start == datetime(2025, 6, 2, 4, 0, tzinfo=UTC)
    assert intervals[0].end == datetime(2025, 6, 2, 5, 0, tzinfo=UTC)


def test_filter_gaps_min_duration() -> None:
    gaps = [
        TimeInterval(start=_utc(9), end=_utc(9, 30)),
        TimeInterval(start=_utc(10), end=_utc(11)),
    ]
    assert filter_gaps_min_duration(gaps, 45) == [
        TimeInterval(start=_utc(10), end=_utc(11))
    ]
