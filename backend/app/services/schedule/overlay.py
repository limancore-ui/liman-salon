from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Literal

from app.db.models.blocked_period import BlockedPeriod
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.services.schedule.errors import ScheduleNotFoundError, ScheduleValidationError
from app.services.schedule.repository import ScheduleRepository
from app.services.schedule.service import ScheduleService
from app.services.schedule.types_impact import (
    BlockedPeriodCreateOverlay,
    BlockedPeriodUpdateOverlay,
    ScheduleOverlay,
    ScheduleRef,
    WorkingHourCreateOverlay,
    WorkingHourUpdateOverlay,
    _UNSET,
    staff_service_link_content_hash,
)
from app.services.service_catalog.repository import ServiceCatalogRepository
from app.services.staff.repository import StaffRepository

ChangeKind = Literal[
    "working_hours.create",
    "working_hours.update",
    "working_hours.delete",
    "blocked_period.create",
    "blocked_period.update",
    "blocked_period.delete",
    "staff_service.detach",
]


@dataclass(frozen=True, slots=True)
class ScheduleImpactChange:
    kind: ChangeKind


@dataclass(frozen=True, slots=True)
class WorkingHoursCreateChange(ScheduleImpactChange):
    kind: Literal["working_hours.create"] = "working_hours.create"
    staff_id: uuid.UUID | None = None
    day_of_week: int = 0
    start_time: time = time(9, 0)
    end_time: time = time(17, 0)
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class WorkingHoursUpdateChange(ScheduleImpactChange):
    kind: Literal["working_hours.update"] = "working_hours.update"
    working_hours_id: uuid.UUID = uuid.UUID(int=0)
    staff_id: uuid.UUID | None = None
    day_of_week: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    set_staff_id: bool = False
    set_effective_from: bool = False
    set_effective_to: bool = False


@dataclass(frozen=True, slots=True)
class WorkingHoursDeleteChange(ScheduleImpactChange):
    kind: Literal["working_hours.delete"] = "working_hours.delete"
    working_hours_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True, slots=True)
class BlockedPeriodCreateChange(ScheduleImpactChange):
    kind: Literal["blocked_period.create"] = "blocked_period.create"
    staff_id: uuid.UUID | None = None
    starts_at: datetime = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
    ends_at: datetime = datetime.fromisoformat("2026-01-01T01:00:00+00:00")
    block_type: str = "manual"


@dataclass(frozen=True, slots=True)
class BlockedPeriodUpdateChange(ScheduleImpactChange):
    kind: Literal["blocked_period.update"] = "blocked_period.update"
    blocked_period_id: uuid.UUID = uuid.UUID(int=0)
    staff_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    set_staff_id: bool = False


@dataclass(frozen=True, slots=True)
class BlockedPeriodDeleteChange(ScheduleImpactChange):
    kind: Literal["blocked_period.delete"] = "blocked_period.delete"
    blocked_period_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True, slots=True)
class StaffServiceDetachChange(ScheduleImpactChange):
    kind: Literal["staff_service.detach"] = "staff_service.detach"
    staff_id: uuid.UUID = uuid.UUID(int=0)
    service_id: uuid.UUID = uuid.UUID(int=0)


@dataclass(frozen=True, slots=True)
class OverlayBuildResult:
    overlay: ScheduleOverlay
    affected_staff_ids: tuple[uuid.UUID, ...]
    schedule_refs: tuple[ScheduleRef, ...]


def build_overlay_from_change(
    *,
    salon_id: uuid.UUID,
    change: ScheduleImpactChange,
    schedule_repo: ScheduleRepository,
    staff_repo: StaffRepository,
    catalog_repo: ServiceCatalogRepository,
) -> OverlayBuildResult:
    schedule_refs: list[ScheduleRef] = []
    overlay = ScheduleOverlay()
    affected: set[uuid.UUID] = set()

    if isinstance(change, WorkingHoursCreateChange):
        ScheduleService._validate_working_hour(
            day_of_week=change.day_of_week,
            start_time=change.start_time,
            end_time=change.end_time,
            effective_from=change.effective_from,
            effective_to=change.effective_to,
        )
        if change.staff_id is not None:
            _ensure_staff(staff_repo, salon_id=salon_id, staff_id=change.staff_id)
            affected.add(change.staff_id)
        else:
            affected.update(_bookable_staff_ids(staff_repo, salon_id))
        create = WorkingHourCreateOverlay(
            staff_id=change.staff_id,
            day_of_week=change.day_of_week,
            start_time=change.start_time,
            end_time=change.end_time,
            effective_from=change.effective_from,
            effective_to=change.effective_to,
        )
        overlay = ScheduleOverlay(working_hours_creates=(create,))
        schedule_refs.append(
            ScheduleRef(
                kind="working_hours",
                id=None,
                updated_at=None,
                content_hash=create.content_hash(),
            )
        )

    elif isinstance(change, WorkingHoursUpdateChange):
        row = schedule_repo.get_working_hour_by_id(
            salon_id=salon_id, working_hours_id=change.working_hours_id
        )
        if row is None:
            raise ScheduleNotFoundError("working hours not found")
        schedule_refs.append(_wh_ref(row))
        merged = _merged_working_hour(row, change)
        ScheduleService._validate_working_hour(
            day_of_week=merged.day_of_week,
            start_time=merged.start_time,
            end_time=merged.end_time,
            effective_from=merged.effective_from,
            effective_to=merged.effective_to,
        )
        if merged.staff_id is not None:
            _ensure_staff(staff_repo, salon_id=salon_id, staff_id=merged.staff_id)
            affected.add(merged.staff_id)
        else:
            affected.update(_bookable_staff_ids(staff_repo, salon_id))
        upd = WorkingHourUpdateOverlay(
            working_hours_id=change.working_hours_id,
            staff_id=change.staff_id if change.set_staff_id else _UNSET,
            day_of_week=change.day_of_week if change.day_of_week is not None else _UNSET,
            start_time=change.start_time if change.start_time is not None else _UNSET,
            end_time=change.end_time if change.end_time is not None else _UNSET,
            effective_from=change.effective_from if change.set_effective_from else _UNSET,
            effective_to=change.effective_to if change.set_effective_to else _UNSET,
            set_staff_id=change.set_staff_id,
            set_effective_from=change.set_effective_from,
            set_effective_to=change.set_effective_to,
        )
        overlay = ScheduleOverlay(working_hours_updates=(upd,))

    elif isinstance(change, WorkingHoursDeleteChange):
        row = schedule_repo.get_working_hour_by_id(
            salon_id=salon_id, working_hours_id=change.working_hours_id
        )
        if row is None:
            raise ScheduleNotFoundError("working hours not found")
        schedule_refs.append(_wh_ref(row))
        if row.staff_id is not None:
            affected.add(row.staff_id)
        else:
            affected.update(_bookable_staff_ids(staff_repo, salon_id))
        overlay = ScheduleOverlay(
            working_hours_deletes=frozenset({change.working_hours_id})
        )

    elif isinstance(change, BlockedPeriodCreateChange):
        starts_at = ScheduleService._normalize_instant(change.starts_at)
        ends_at = ScheduleService._normalize_instant(change.ends_at)
        ScheduleService._validate_blocked_period(
            starts_at=starts_at,
            ends_at=ends_at,
            block_type=change.block_type,
        )
        if change.staff_id is not None:
            _ensure_staff(staff_repo, salon_id=salon_id, staff_id=change.staff_id)
            affected.add(change.staff_id)
        else:
            affected.update(_bookable_staff_ids(staff_repo, salon_id))
        create = BlockedPeriodCreateOverlay(
            staff_id=change.staff_id,
            starts_at=starts_at,
            ends_at=ends_at,
            block_type=change.block_type,
        )
        overlay = ScheduleOverlay(blocked_period_creates=(create,))
        schedule_refs.append(
            ScheduleRef(
                kind="blocked_period",
                id=None,
                updated_at=None,
                content_hash=create.content_hash(),
            )
        )

    elif isinstance(change, BlockedPeriodUpdateChange):
        row = schedule_repo.get_blocked_period_by_id(
            salon_id=salon_id, blocked_period_id=change.blocked_period_id
        )
        if row is None:
            raise ScheduleNotFoundError("blocked period not found")
        schedule_refs.append(_bp_ref(row))
        merged = _merged_blocked_period(row, change)
        ScheduleService._validate_blocked_period(
            starts_at=merged.starts_at,
            ends_at=merged.ends_at,
            block_type=merged.block_type,
        )
        if merged.staff_id is not None:
            _ensure_staff(staff_repo, salon_id=salon_id, staff_id=merged.staff_id)
            affected.add(merged.staff_id)
        else:
            affected.update(_bookable_staff_ids(staff_repo, salon_id))
        upd = BlockedPeriodUpdateOverlay(
            blocked_period_id=change.blocked_period_id,
            staff_id=change.staff_id,
            starts_at=change.starts_at,
            ends_at=change.ends_at,
            set_staff_id=change.set_staff_id,
        )
        overlay = ScheduleOverlay(blocked_period_updates=(upd,))

    elif isinstance(change, BlockedPeriodDeleteChange):
        row = schedule_repo.get_blocked_period_by_id(
            salon_id=salon_id, blocked_period_id=change.blocked_period_id
        )
        if row is None:
            raise ScheduleNotFoundError("blocked period not found")
        schedule_refs.append(_bp_ref(row))
        if row.staff_id is not None:
            affected.add(row.staff_id)
        else:
            affected.update(_bookable_staff_ids(staff_repo, salon_id))
        overlay = ScheduleOverlay(
            blocked_period_deletes=frozenset({change.blocked_period_id})
        )

    elif isinstance(change, StaffServiceDetachChange):
        service = catalog_repo.get_service_by_id(
            salon_id=salon_id, service_id=change.service_id
        )
        if service is None:
            raise ScheduleNotFoundError("service not found")
        _ensure_staff(staff_repo, salon_id=salon_id, staff_id=change.staff_id)
        link = catalog_repo.get_staff_service_link(
            salon_id=salon_id,
            staff_id=change.staff_id,
            service_id=change.service_id,
        )
        if link is None:
            raise ScheduleNotFoundError("staff service link not found")
        schedule_refs.append(_staff_service_ref(link))
        affected.add(change.staff_id)
        overlay = ScheduleOverlay(
            staff_service_detaches=frozenset({(change.staff_id, change.service_id)})
        )
    else:
        raise ScheduleValidationError("unsupported change kind")

    sorted_refs = tuple(
        sorted(
            schedule_refs,
            key=lambda r: (r.kind, str(r.id) if r.id else ""),
        )
    )
    return OverlayBuildResult(
        overlay=overlay,
        affected_staff_ids=tuple(sorted(affected)),
        schedule_refs=sorted_refs,
    )


def _bookable_staff_ids(staff_repo: StaffRepository, salon_id: uuid.UUID) -> set[uuid.UUID]:
    return {s.id for s in staff_repo.list_staff(salon_id=salon_id, bookable_only=True)}


def _ensure_staff(
    staff_repo: StaffRepository, *, salon_id: uuid.UUID, staff_id: uuid.UUID
) -> None:
    if staff_repo.get_staff_by_id(salon_id=salon_id, staff_id=staff_id) is None:
        raise ScheduleNotFoundError("staff not found")


def _wh_ref(row: WorkingHour) -> ScheduleRef:
    return ScheduleRef(
        kind="working_hours",
        id=row.id,
        updated_at=row.updated_at,
        content_hash=None,
    )


def _bp_ref(row: BlockedPeriod) -> ScheduleRef:
    return ScheduleRef(
        kind="blocked_period",
        id=row.id,
        updated_at=row.updated_at,
        content_hash=None,
    )


def _staff_service_ref(link: StaffService) -> ScheduleRef:
    updated_at = getattr(link, "updated_at", None)
    content_hash = None
    if updated_at is None:
        content_hash = staff_service_link_content_hash(
            staff_id=link.staff_id,
            service_id=link.service_id,
            created_at=link.created_at,
        )
    return ScheduleRef(
        kind="staff_service",
        id=link.id,
        updated_at=updated_at,
        content_hash=content_hash,
    )


@dataclass(frozen=True, slots=True)
class _MergedWorkingHour:
    staff_id: uuid.UUID | None
    day_of_week: int
    start_time: time
    end_time: time
    effective_from: date | None
    effective_to: date | None


@dataclass(frozen=True, slots=True)
class _MergedBlockedPeriod:
    staff_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    block_type: str


def _merged_working_hour(
    row: WorkingHour, change: WorkingHoursUpdateChange
) -> _MergedWorkingHour:
    """Merge update onto loaded row without mutating the ORM instance (preview-safe)."""
    staff_id = change.staff_id if change.set_staff_id else row.staff_id
    day_of_week = (
        change.day_of_week if change.day_of_week is not None else row.day_of_week
    )
    start_time = change.start_time if change.start_time is not None else row.start_time
    end_time = change.end_time if change.end_time is not None else row.end_time
    effective_from = (
        change.effective_from if change.set_effective_from else row.effective_from
    )
    effective_to = change.effective_to if change.set_effective_to else row.effective_to
    return _MergedWorkingHour(
        staff_id=staff_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _merged_blocked_period(
    row: BlockedPeriod, change: BlockedPeriodUpdateChange
) -> _MergedBlockedPeriod:
    """Merge update onto loaded row without mutating the ORM instance (preview-safe)."""
    staff_id = change.staff_id if change.set_staff_id else row.staff_id
    starts_at = (
        ScheduleService._normalize_instant(change.starts_at)
        if change.starts_at is not None
        else row.starts_at
    )
    ends_at = (
        ScheduleService._normalize_instant(change.ends_at)
        if change.ends_at is not None
        else row.ends_at
    )
    return _MergedBlockedPeriod(
        staff_id=staff_id,
        starts_at=starts_at,
        ends_at=ends_at,
        block_type=row.block_type,
    )
