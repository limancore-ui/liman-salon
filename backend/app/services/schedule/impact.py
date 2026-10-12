from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.services.availability.service import AvailabilityService
from app.services.booking.repository import BookingRepository
from app.services.schedule.errors import ScheduleValidationError
from app.services.schedule.overlay import (
    BlockedPeriodCreateChange,
    BlockedPeriodDeleteChange,
    BlockedPeriodUpdateChange,
    ScheduleImpactChange,
    StaffServiceDetachChange,
    WorkingHoursCreateChange,
    WorkingHoursDeleteChange,
    WorkingHoursUpdateChange,
    build_overlay_from_change,
)
from app.services.schedule.repository import ScheduleRepository
from app.services.schedule.types_impact import ImpactReason, ScheduleRef
from app.services.service_catalog.repository import ServiceCatalogRepository
from app.services.staff.repository import StaffRepository

DEFAULT_HORIZON_DAYS = 90
MAX_HORIZON_DAYS = 365
DEFAULT_IMPACT_LIMIT = 50
MAX_IMPACT_LIMIT = 100


@dataclass(frozen=True, slots=True)
class ImpactBookingRow:
    booking_id: uuid.UUID
    status: str
    is_in_progress: bool
    starts_at: datetime
    ends_at: datetime
    staff_id: uuid.UUID
    service_id: uuid.UUID
    customer_name: str
    service_name: str
    reasons: tuple[ImpactReason, ...]


@dataclass(frozen=True, slots=True)
class ImpactPreviewResult:
    as_of: datetime
    change_kind: str
    affected_staff_ids: tuple[uuid.UUID, ...]
    starts_at_from: datetime
    starts_at_to: datetime
    horizon_days: int
    impacts: tuple[ImpactBookingRow, ...]
    all_impacts: tuple[ImpactBookingRow, ...]
    impact_fingerprint: str
    schedule_refs: tuple[ScheduleRef, ...]
    impact_offset: int
    impact_limit: int


class ScheduleImpactService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._schedule_repo = ScheduleRepository(session)
        self._staff_repo = StaffRepository(session)
        self._catalog_repo = ServiceCatalogRepository(session)
        self._booking_repo = BookingRepository(session)
        self._availability = AvailabilityService(session)

    def preview_impact(
        self,
        *,
        salon_id: uuid.UUID,
        change: ScheduleImpactChange,
        as_of: datetime,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        impact_offset: int = 0,
        impact_limit: int = DEFAULT_IMPACT_LIMIT,
    ) -> ImpactPreviewResult:
        if as_of.tzinfo is None:
            raise ScheduleValidationError("as_of must be timezone-aware")
        if horizon_days < 1 or horizon_days > MAX_HORIZON_DAYS:
            raise ScheduleValidationError(
                f"horizon_days must be between 1 and {MAX_HORIZON_DAYS}"
            )
        if impact_offset < 0:
            raise ScheduleValidationError("impact_offset must be non-negative")
        if impact_limit < 1 or impact_limit > MAX_IMPACT_LIMIT:
            raise ScheduleValidationError(
                f"impact_limit must be between 1 and {MAX_IMPACT_LIMIT}"
            )

        overlay_result = build_overlay_from_change(
            salon_id=salon_id,
            change=change,
            schedule_repo=self._schedule_repo,
            staff_repo=self._staff_repo,
            catalog_repo=self._catalog_repo,
        )
        starts_at_from = as_of
        starts_at_to = as_of + timedelta(days=horizon_days)

        candidates = self._booking_repo.list_operational_bookings_for_impact(
            salon_id=salon_id,
            staff_ids=overlay_result.affected_staff_ids,
            as_of=as_of,
            starts_at_to=starts_at_to,
        )

        all_impacts: list[ImpactBookingRow] = []
        for booking in candidates:
            reasons = self._classify_booking(
                salon_id=salon_id,
                change=change,
                overlay=overlay_result.overlay,
                booking=booking,
                as_of=as_of,
            )
            if not reasons:
                continue
            all_impacts.append(
                ImpactBookingRow(
                    booking_id=booking.id,
                    status=booking.status,
                    is_in_progress=booking.status == "in_progress",
                    starts_at=booking.starts_at,
                    ends_at=booking.ends_at,
                    staff_id=booking.staff_id,
                    service_id=booking.service_id,
                    customer_name=booking.customer_name,
                    service_name=booking.service_name,
                    reasons=reasons,
                )
            )

        all_impacts.sort(key=lambda row: (row.starts_at, row.booking_id))
        page = all_impacts[impact_offset : impact_offset + impact_limit]

        fingerprint = compute_impact_fingerprint_v1(
            salon_id=salon_id,
            as_of=as_of,
            horizon_days=horizon_days,
            starts_at_from=starts_at_from,
            starts_at_to=starts_at_to,
            change=change,
            impacts=all_impacts,
            schedule_refs=overlay_result.schedule_refs,
            candidates=candidates,
        )

        return ImpactPreviewResult(
            as_of=as_of,
            change_kind=change.kind,
            affected_staff_ids=overlay_result.affected_staff_ids,
            starts_at_from=starts_at_from,
            starts_at_to=starts_at_to,
            horizon_days=horizon_days,
            impacts=tuple(page),
            all_impacts=tuple(all_impacts),
            impact_fingerprint=fingerprint,
            schedule_refs=overlay_result.schedule_refs,
            impact_offset=impact_offset,
            impact_limit=impact_limit,
        )

    def _classify_booking(
        self,
        *,
        salon_id: uuid.UUID,
        change: ScheduleImpactChange,
        overlay: object,
        booking: object,
        as_of: datetime,
    ) -> tuple[ImpactReason, ...]:
        from app.services.booking.types import OperationalBookingForImpact
        from app.services.schedule.types_impact import ScheduleOverlay

        assert isinstance(booking, OperationalBookingForImpact)
        assert isinstance(overlay, ScheduleOverlay)

        reasons: list[ImpactReason] = []
        available = self._availability.is_occupied_interval_available(
            salon_id=salon_id,
            staff_id=booking.staff_id,
            occupied_start=booking.starts_at,
            occupied_end=booking.ends_at,
            as_of=as_of,
            exclude_booking_id=booking.id,
            overlay=overlay,
        )
        if not available:
            reasons.append("outside_availability")

        if isinstance(change, StaffServiceDetachChange):
            if (
                booking.staff_id == change.staff_id
                and booking.service_id == change.service_id
            ):
                if "staff_no_longer_performs_service" not in reasons:
                    reasons.append("staff_no_longer_performs_service")

        return tuple(sorted(set(reasons)))


def compute_impact_fingerprint_v1(
    *,
    salon_id: uuid.UUID,
    as_of: datetime,
    horizon_days: int,
    starts_at_from: datetime,
    starts_at_to: datetime,
    change: ScheduleImpactChange,
    impacts: list[ImpactBookingRow],
    schedule_refs: tuple[ScheduleRef, ...],
    candidates: list[object],
) -> str:
    from app.services.booking.types import OperationalBookingForImpact

    impacts_sorted = sorted(impacts, key=lambda row: row.booking_id)
    impact_payload = []
    for row in impacts_sorted:
        candidate = _find_candidate(candidates, row.booking_id)
        assert isinstance(candidate, OperationalBookingForImpact)
        impact_payload.append(
            {
                "booking_id": str(row.booking_id),
                "reasons": sorted(row.reasons),
                "booking_state": {
                    "status": candidate.status,
                    "starts_at": candidate.starts_at.isoformat(),
                    "ends_at": candidate.ends_at.isoformat(),
                    "staff_id": str(candidate.staff_id),
                    "service_id": str(candidate.service_id),
                    "expires_at": (
                        candidate.expires_at.isoformat()
                        if candidate.expires_at is not None
                        else None
                    ),
                    "updated_at": candidate.updated_at.isoformat(),
                },
            }
        )

    refs_payload = []
    for ref in sorted(
        schedule_refs,
        key=lambda r: (r.kind, str(r.id) if r.id else ""),
    ):
        refs_payload.append(
            {
                "kind": ref.kind,
                "id": str(ref.id) if ref.id is not None else None,
                "updated_at": (
                    ref.updated_at.isoformat() if ref.updated_at is not None else None
                ),
                "content_hash": ref.content_hash,
            }
        )

    payload: dict[str, Any] = {
        "v": 1,
        "salon_id": str(salon_id),
        "as_of": as_of.isoformat(),
        "horizon": {
            "days": horizon_days,
            "starts_at_from": starts_at_from.isoformat(),
            "starts_at_to": starts_at_to.isoformat(),
        },
        "change": _change_to_fingerprint_dict(change),
        "impacts": impact_payload,
        "schedule_refs": refs_payload,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_candidate(
    candidates: list[object], booking_id: uuid.UUID
) -> OperationalBookingForImpact:
    from app.services.booking.types import OperationalBookingForImpact

    for candidate in candidates:
        assert isinstance(candidate, OperationalBookingForImpact)
        if candidate.id == booking_id:
            return candidate
    raise ValueError("impact booking missing from candidate set")


def _change_to_fingerprint_dict(change: ScheduleImpactChange) -> dict[str, Any]:
    if isinstance(change, WorkingHoursCreateChange):
        return {
            "kind": change.kind,
            "staff_id": _optional_uuid(change.staff_id),
            "day_of_week": change.day_of_week,
            "start_time": change.start_time.isoformat(),
            "end_time": change.end_time.isoformat(),
            "effective_from": _optional_date(change.effective_from),
            "effective_to": _optional_date(change.effective_to),
        }
    if isinstance(change, WorkingHoursUpdateChange):
        body: dict[str, Any] = {
            "kind": change.kind,
            "working_hours_id": str(change.working_hours_id),
        }
        if change.set_staff_id:
            body["staff_id"] = _optional_uuid(change.staff_id)
        if change.day_of_week is not None:
            body["day_of_week"] = change.day_of_week
        if change.start_time is not None:
            body["start_time"] = change.start_time.isoformat()
        if change.end_time is not None:
            body["end_time"] = change.end_time.isoformat()
        if change.set_effective_from:
            body["effective_from"] = _optional_date(change.effective_from)
        if change.set_effective_to:
            body["effective_to"] = _optional_date(change.effective_to)
        return body
    if isinstance(change, WorkingHoursDeleteChange):
        return {
            "kind": change.kind,
            "working_hours_id": str(change.working_hours_id),
        }
    if isinstance(change, BlockedPeriodCreateChange):
        return {
            "kind": change.kind,
            "staff_id": _optional_uuid(change.staff_id),
            "starts_at": change.starts_at.isoformat(),
            "ends_at": change.ends_at.isoformat(),
            "block_type": change.block_type,
        }
    if isinstance(change, BlockedPeriodUpdateChange):
        body = {
            "kind": change.kind,
            "blocked_period_id": str(change.blocked_period_id),
        }
        if change.set_staff_id:
            body["staff_id"] = _optional_uuid(change.staff_id)
        if change.starts_at is not None:
            body["starts_at"] = change.starts_at.isoformat()
        if change.ends_at is not None:
            body["ends_at"] = change.ends_at.isoformat()
        return body
    if isinstance(change, BlockedPeriodDeleteChange):
        return {
            "kind": change.kind,
            "blocked_period_id": str(change.blocked_period_id),
        }
    if isinstance(change, StaffServiceDetachChange):
        return {
            "kind": change.kind,
            "staff_id": str(change.staff_id),
            "service_id": str(change.service_id),
        }
    raise ScheduleValidationError("unsupported change kind")


def _optional_uuid(value: uuid.UUID | None) -> str | None:
    return str(value) if value is not None else None


def _optional_date(value: object) -> str | None:
    if value is None:
        return None
    return value.isoformat()  # type: ignore[union-attr]
