from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.availability.types import (
    BusyInterval,
    ServiceAvailabilitySlot,
    TimeInterval,
    WorkingHourSpec,
)

# MVP public booking grid when no salon-level step is configured.
DEFAULT_SERVICE_SLOT_STEP_MINUTES = 30


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


def gap_fits_service_net_placement(
    gap: TimeInterval,
    *,
    duration_minutes: int,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
) -> bool:
    """True when at least one NET service placement fits inside the gap (no grid step)."""
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    min_occupied = buffer_before_minutes + duration_minutes + buffer_after_minutes
    if (gap.end - gap.start) < timedelta(minutes=min_occupied):
        return False
    buf_before = timedelta(minutes=buffer_before_minutes)
    buf_after = timedelta(minutes=buffer_after_minutes)
    service_len = timedelta(minutes=duration_minutes)
    min_start = gap.start + buf_before
    max_start = gap.end - buf_after - service_len
    return max_start >= min_start


def _ceil_local_datetime_to_step(
    dt: datetime,
    tz: ZoneInfo,
    step_minutes: int,
) -> datetime:
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    local = dt.astimezone(tz)
    day_start = datetime.combine(local.date(), time.min, tzinfo=tz)
    elapsed = local - day_start
    total_seconds = int(elapsed.total_seconds())
    if local.microsecond:
        total_seconds += 1
    step_seconds = step_minutes * 60
    remainder = total_seconds % step_seconds
    if remainder == 0 and local.second == 0 and local.microsecond == 0:
        aligned_local = local.replace(second=0, microsecond=0)
    else:
        add_seconds = step_seconds - remainder
        aligned_local = day_start + timedelta(seconds=total_seconds + add_seconds)
    return aligned_local.astimezone(ZoneInfo("UTC"))


def net_service_slots_from_free_gaps(
    gaps: list[TimeInterval],
    *,
    duration_minutes: int,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
    slot_step_minutes: int = DEFAULT_SERVICE_SLOT_STEP_MINUTES,
    tz: ZoneInfo | None = None,
) -> list[ServiceAvailabilitySlot]:
    """
    Map raw free gaps to discrete NET service start times.

    Bookings are already subtracted using stored occupied bounds; each start must
    fit buffer_before + duration + buffer_after inside the gap. Starts advance on a
    fixed minute grid (salon timezone when ``tz`` is set, otherwise UTC).
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")
    if slot_step_minutes <= 0:
        raise ValueError("slot_step_minutes must be positive")
    grid_tz = tz if tz is not None else ZoneInfo("UTC")
    min_occupied = buffer_before_minutes + duration_minutes + buffer_after_minutes
    eligible = filter_gaps_min_duration(gaps, min_occupied)
    slots: list[ServiceAvailabilitySlot] = []
    buf_before = timedelta(minutes=buffer_before_minutes)
    buf_after = timedelta(minutes=buffer_after_minutes)
    service_len = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=slot_step_minutes)
    for gap in eligible:
        min_start = gap.start + buf_before
        max_start = gap.end - buf_after - service_len
        if max_start < min_start:
            continue
        cursor = _ceil_local_datetime_to_step(min_start, grid_tz, slot_step_minutes)
        while cursor <= max_start:
            slots.append(
                ServiceAvailabilitySlot(
                    service_start=cursor,
                    service_end=cursor + service_len,
                )
            )
            cursor += step
    return slots


def first_bookable_net_start_on_or_after(
    gap: TimeInterval,
    *,
    duration_minutes: int,
    buffer_before_minutes: int,
    buffer_after_minutes: int,
    not_before: datetime,
    tz: ZoneInfo,
    slot_step_minutes: int = DEFAULT_SERVICE_SLOT_STEP_MINUTES,
) -> datetime | None:
    """Earliest discrete NET start in ``gap`` at or after ``not_before`` (Availability Core grid)."""
    for slot in net_service_slots_from_free_gaps(
        [gap],
        duration_minutes=duration_minutes,
        buffer_before_minutes=buffer_before_minutes,
        buffer_after_minutes=buffer_after_minutes,
        slot_step_minutes=slot_step_minutes,
        tz=tz,
    ):
        if slot.service_start >= not_before:
            return slot.service_start
    return None


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
