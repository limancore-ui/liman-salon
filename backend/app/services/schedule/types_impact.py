from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Literal

from app.services.availability.types import BusyInterval, WorkingHourSpec

ImpactReason = Literal["outside_availability", "staff_no_longer_performs_service"]

_UNSET = object()


@dataclass(frozen=True, slots=True)
class WorkingHourCreateOverlay:
    staff_id: uuid.UUID | None
    day_of_week: int
    start_time: time
    end_time: time
    effective_from: date | None = None
    effective_to: date | None = None

    def to_spec(self) -> WorkingHourSpec:
        return WorkingHourSpec(
            day_of_week=self.day_of_week,
            start_time=self.start_time,
            end_time=self.end_time,
            staff_id=self.staff_id,
            effective_from=self.effective_from,
            effective_to=self.effective_to,
        )

    def content_hash(self) -> str:
        return _content_hash(
            {
                "staff_id": _uuid_str(self.staff_id),
                "day_of_week": self.day_of_week,
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "effective_from": _date_str(self.effective_from),
                "effective_to": _date_str(self.effective_to),
            }
        )


@dataclass(frozen=True, slots=True)
class WorkingHourUpdateOverlay:
    working_hours_id: uuid.UUID
    staff_id: uuid.UUID | None | object = field(default=_UNSET, repr=False)
    day_of_week: int | object = field(default=_UNSET, repr=False)
    start_time: time | object = field(default=_UNSET, repr=False)
    end_time: time | object = field(default=_UNSET, repr=False)
    effective_from: date | None | object = field(default=_UNSET, repr=False)
    effective_to: date | None | object = field(default=_UNSET, repr=False)
    set_staff_id: bool = False
    set_effective_from: bool = False
    set_effective_to: bool = False


@dataclass(frozen=True, slots=True)
class BlockedPeriodCreateOverlay:
    staff_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    block_type: str = "manual"

    def to_busy_interval(self) -> BusyInterval:
        return BusyInterval(start=self.starts_at, end=self.ends_at)

    def content_hash(self) -> str:
        return _content_hash(
            {
                "staff_id": _uuid_str(self.staff_id),
                "starts_at": self.starts_at.isoformat(),
                "ends_at": self.ends_at.isoformat(),
                "block_type": self.block_type,
            }
        )


@dataclass(frozen=True, slots=True)
class BlockedPeriodUpdateOverlay:
    blocked_period_id: uuid.UUID
    staff_id: uuid.UUID | None | object = field(default=_UNSET, repr=False)
    starts_at: datetime | object = field(default=_UNSET, repr=False)
    ends_at: datetime | object = field(default=_UNSET, repr=False)
    set_staff_id: bool = False


@dataclass(frozen=True, slots=True)
class StaffServiceDetachOverlay:
    staff_id: uuid.UUID
    service_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ScheduleOverlay:
    """In-memory schedule simulation applied on availability reads only."""

    working_hours_creates: tuple[WorkingHourCreateOverlay, ...] = ()
    working_hours_updates: tuple[WorkingHourUpdateOverlay, ...] = ()
    working_hours_deletes: frozenset[uuid.UUID] = frozenset()
    blocked_period_creates: tuple[BlockedPeriodCreateOverlay, ...] = ()
    blocked_period_updates: tuple[BlockedPeriodUpdateOverlay, ...] = ()
    blocked_period_deletes: frozenset[uuid.UUID] = frozenset()
    staff_service_detaches: frozenset[tuple[uuid.UUID, uuid.UUID]] = frozenset()


@dataclass(frozen=True, slots=True)
class ScheduleRef:
    kind: Literal["working_hours", "blocked_period"]
    id: uuid.UUID | None
    updated_at: datetime | None
    content_hash: str | None


def _uuid_str(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None


def _date_str(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _content_hash(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
