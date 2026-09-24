from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.availability.types import BusyInterval, TimeInterval, WorkingHourSpec


def _hour_row_applies_on_date(row: WorkingHourSpec, local_date: date) -> bool:
    if row.effective_from is not None and local_date < row.effective_from:
        return False
    if row.effective_to is not None and local_date > row.effective_to:
        return False
    return True


def local_time_window_to_utc_interval(
    local_date: date,
    start_time: time,
    end_time: time,
    tz: ZoneInfo,
) -> TimeInterval:
    start_local = datetime.combine(local_date, start_time, tzinfo=tz)
    end_local = datetime.combine(local_date, end_time, tzinfo=tz)
    return TimeInterval(
        start=start_local.astimezone(ZoneInfo("UTC")),
        end=end_local.astimezone(ZoneInfo("UTC")),
    )


def build_working_intervals_for_day(
    local_date: date,
    salon_defaults: list[WorkingHourSpec],
    staff_specific: list[WorkingHourSpec],
    tz: ZoneInfo,
) -> list[TimeInterval]:
    """Staff-specific rows override salon defaults for the same day_of_week when any apply."""
    dow = local_date.weekday()
    salon_for_day = [
        r
        for r in salon_defaults
        if r.day_of_week == dow and r.staff_id is None and _hour_row_applies_on_date(r, local_date)
    ]
    staff_for_day = [
        r
        for r in staff_specific
        if r.day_of_week == dow and r.staff_id is not None and _hour_row_applies_on_date(r, local_date)
    ]
    rows = staff_for_day if staff_for_day else salon_for_day
    intervals = [
        local_time_window_to_utc_interval(local_date, r.start_time, r.end_time, tz)
        for r in rows
    ]
    return merge_intervals(intervals)


def build_working_intervals_for_range(
    start_date: date,
    end_date: date,
    salon_defaults: list[WorkingHourSpec],
    staff_specific: list[WorkingHourSpec],
    tz: ZoneInfo,
) -> list[TimeInterval]:
    if end_date < start_date:
        return []
    out: list[TimeInterval] = []
    current = start_date
    while current <= end_date:
        out.extend(
            build_working_intervals_for_day(current, salon_defaults, staff_specific, tz)
        )
        current += timedelta(days=1)
    return merge_intervals(out)


def merge_intervals(intervals: list[TimeInterval]) -> list[TimeInterval]:
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda i: i.start)
    merged: list[TimeInterval] = [sorted_iv[0]]
    for iv in sorted_iv[1:]:
        last = merged[-1]
        if iv.start <= last.end:
            merged[-1] = TimeInterval(start=last.start, end=max(last.end, iv.end))
        else:
            merged.append(iv)
    return merged


def _subtract_one(base: TimeInterval, cut: TimeInterval) -> list[TimeInterval]:
    if cut.end <= base.start or cut.start >= base.end:
        return [base]
    pieces: list[TimeInterval] = []
    if cut.start > base.start:
        pieces.append(TimeInterval(start=base.start, end=cut.start))
    if cut.end < base.end:
        pieces.append(TimeInterval(start=cut.end, end=base.end))
    return pieces


def subtract_busy_from_working(
    working: list[TimeInterval],
    busy: list[BusyInterval | TimeInterval],
) -> list[TimeInterval]:
    busy_merged = merge_intervals(
        [TimeInterval(start=b.start, end=b.end) for b in busy]
    )
    free = working
    for block in busy_merged:
        next_free: list[TimeInterval] = []
        for segment in free:
            next_free.extend(_subtract_one(segment, block))
        free = merge_intervals(next_free)
    return free


def clip_intervals_to_range(
    intervals: list[TimeInterval],
    range_start: datetime,
    range_end: datetime,
) -> list[TimeInterval]:
    """Clip to half-open [range_start, range_end)."""
    clipped: list[TimeInterval] = []
    for iv in intervals:
        start = max(iv.start, range_start)
        end = min(iv.end, range_end)
        if start < end:
            clipped.append(TimeInterval(start=start, end=end))
    return merge_intervals(clipped)


def filter_gaps_min_duration(
    gaps: list[TimeInterval],
    duration_minutes: int,
) -> list[TimeInterval]:
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    min_len = timedelta(minutes=duration_minutes)
    return [g for g in gaps if (g.end - g.start) >= min_len]


def salon_local_date_range_to_utc_bounds(
    start_date: date,
    end_date: date,
    tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    """UTC bounds for half-open [start of start_date, start of day after end_date) in salon TZ."""
    range_start = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(
        ZoneInfo("UTC")
    )
    range_end = datetime.combine(
        end_date + timedelta(days=1), time.min, tzinfo=tz
    ).astimezone(ZoneInfo("UTC"))
    return range_start, range_end
