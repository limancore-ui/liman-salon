from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.availability.repository import AvailabilityRepository
from app.services.availability.service import AvailabilityService
from app.services.booking.repository import BookingRepository
from app.services.booking.types import OperationalBookingForImpact
from app.services.schedule.impact import (
    ImpactBookingRow,
    ScheduleImpactService,
    compute_impact_fingerprint_v1,
)
from app.services.schedule.overlay import (
    BlockedPeriodCreateChange,
    BlockedPeriodUpdateChange,
    StaffServiceDetachChange,
    WorkingHoursCreateChange,
    WorkingHoursDeleteChange,
    WorkingHoursUpdateChange,
    build_overlay_from_change,
)
from app.services.schedule.repository import ScheduleRepository
from app.services.schedule.types_impact import (
    BlockedPeriodCreateOverlay,
    ScheduleOverlay,
    ScheduleRef,
    WorkingHourCreateOverlay,
    staff_service_link_content_hash,
)
from app.services.service_catalog.repository import ServiceCatalogRepository
from app.services.staff.repository import StaffRepository

UTC = timezone.utc
SALON_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STAFF_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
BOOKING_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
SERVICE_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


def _operational_booking(**kwargs: object) -> OperationalBookingForImpact:
    defaults = {
        "id": BOOKING_ID,
        "status": "confirmed",
        "starts_at": datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        "staff_id": STAFF_ID,
        "service_id": SERVICE_ID,
        "expires_at": None,
        "updated_at": datetime(2026, 7, 1, 9, 0, tzinfo=UTC),
        "customer_name": "Client",
        "service_name": "Cut",
    }
    defaults.update(kwargs)
    return OperationalBookingForImpact(**defaults)  # type: ignore[arg-type]


def test_operational_impact_filters_builds_without_name_error() -> None:
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    filters = BookingRepository._operational_impact_filters(
        salon_id=SALON_ID,
        staff_ids=(STAFF_ID,),
        as_of=as_of,
        starts_at_to=as_of + timedelta(days=90),
    )
    assert len(filters) == 4


def test_operational_impact_horizon_predicate_requires_starts_at_from_as_of() -> None:
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.db.models.booking import Booking

    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    starts_at_to = as_of + timedelta(days=90)
    filters = BookingRepository._operational_impact_filters(
        salon_id=SALON_ID,
        staff_ids=(STAFF_ID,),
        as_of=as_of,
        starts_at_to=starts_at_to,
    )
    sql = str(
        select(Booking.id)
        .where(*filters)
        .compile(dialect=postgresql.dialect())
    )
    compact = sql.replace(" ", "")
    assert "starts_at>=" in compact
    assert "ends_at>" in compact


def test_fingerprint_changes_when_staff_service_schedule_ref_changes() -> None:
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    change = StaffServiceDetachChange(staff_id=STAFF_ID, service_id=SERVICE_ID)
    link_id = uuid.UUID("99999999-9999-4999-8999-999999999999")
    created_a = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)
    created_b = datetime(2026, 6, 2, 8, 0, tzinfo=UTC)
    ref_a = ScheduleRef(
        kind="staff_service",
        id=link_id,
        updated_at=None,
        content_hash=staff_service_link_content_hash(
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            created_at=created_a,
        ),
    )
    ref_b = ScheduleRef(
        kind="staff_service",
        id=link_id,
        updated_at=None,
        content_hash=staff_service_link_content_hash(
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            created_at=created_b,
        ),
    )
    kwargs = dict(
        salon_id=SALON_ID,
        as_of=as_of,
        horizon_days=90,
        starts_at_from=as_of,
        starts_at_to=as_of + timedelta(days=90),
        change=change,
        impacts=[],
        candidates=[],
    )
    fp_a = compute_impact_fingerprint_v1(**kwargs, schedule_refs=(ref_a,))
    fp_b = compute_impact_fingerprint_v1(**kwargs, schedule_refs=(ref_b,))
    assert fp_a != fp_b


def test_build_overlay_detach_appends_staff_service_schedule_ref() -> None:
    link_id = uuid.UUID("88888888-8888-4888-8888-888888888888")
    link = SimpleNamespace(
        id=link_id,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        created_at=datetime(2026, 6, 1, 8, 0, tzinfo=UTC),
    )
    session = MagicMock()
    schedule_repo = ScheduleRepository(session)
    staff_repo = StaffRepository(session)
    staff_repo.get_staff_by_id = MagicMock(return_value=MagicMock())
    catalog_repo = ServiceCatalogRepository(session)
    catalog_repo.get_service_by_id = MagicMock(return_value=MagicMock())
    catalog_repo.get_staff_service_link = MagicMock(return_value=link)

    result = build_overlay_from_change(
        salon_id=SALON_ID,
        change=StaffServiceDetachChange(staff_id=STAFF_ID, service_id=SERVICE_ID),
        schedule_repo=schedule_repo,
        staff_repo=staff_repo,
        catalog_repo=catalog_repo,
    )
    assert len(result.schedule_refs) == 1
    ref = result.schedule_refs[0]
    assert ref.kind == "staff_service"
    assert ref.id == link_id
    assert ref.content_hash is not None


def test_fingerprint_stable_and_independent_of_pagination_offset() -> None:
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    change = WorkingHoursDeleteChange(
        working_hours_id=uuid.UUID("11111111-1111-4111-8111-111111111111")
    )
    impacts = [
        ImpactBookingRow(
            booking_id=BOOKING_ID,
            status="confirmed",
            is_in_progress=False,
            starts_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
            ends_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            customer_name="Client",
            service_name="Cut",
            reasons=("outside_availability",),
        )
    ]
    candidates = [_operational_booking()]
    fp1 = compute_impact_fingerprint_v1(
        salon_id=SALON_ID,
        as_of=as_of,
        horizon_days=90,
        starts_at_from=as_of,
        starts_at_to=as_of + timedelta(days=90),
        change=change,
        impacts=impacts,
        schedule_refs=(),
        candidates=candidates,
    )
    fp2 = compute_impact_fingerprint_v1(
        salon_id=SALON_ID,
        as_of=as_of,
        horizon_days=90,
        starts_at_from=as_of,
        starts_at_to=as_of + timedelta(days=90),
        change=change,
        impacts=impacts,
        schedule_refs=(),
        candidates=candidates,
    )
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_changes_when_booking_updated_at_changes() -> None:
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    change = StaffServiceDetachChange(staff_id=STAFF_ID, service_id=SERVICE_ID)
    impacts = [
        ImpactBookingRow(
            booking_id=BOOKING_ID,
            status="confirmed",
            is_in_progress=False,
            starts_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
            ends_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            customer_name="Client",
            service_name="Cut",
            reasons=("staff_no_longer_performs_service",),
        )
    ]
    candidate_a = _operational_booking(
        updated_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    )
    candidate_b = _operational_booking(
        updated_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    )
    kwargs = dict(
        salon_id=SALON_ID,
        as_of=as_of,
        horizon_days=90,
        starts_at_from=as_of,
        starts_at_to=as_of + timedelta(days=90),
        change=change,
        impacts=impacts,
        schedule_refs=(),
    )
    fp_a = compute_impact_fingerprint_v1(**kwargs, candidates=[candidate_a])
    fp_b = compute_impact_fingerprint_v1(**kwargs, candidates=[candidate_b])
    assert fp_a != fp_b


def test_classify_detach_adds_staff_reason() -> None:
    session = MagicMock()
    svc = ScheduleImpactService(session)
    change = StaffServiceDetachChange(staff_id=STAFF_ID, service_id=SERVICE_ID)
    booking = _operational_booking()
    svc._availability = MagicMock()
    svc._availability.is_occupied_interval_available.return_value = True
    reasons = svc._classify_booking(
        salon_id=SALON_ID,
        change=change,
        overlay=ScheduleOverlay(
            staff_service_detaches=frozenset({(STAFF_ID, SERVICE_ID)})
        ),
        booking=booking,
        as_of=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
    )
    assert reasons == ("staff_no_longer_performs_service",)


def test_classify_outside_availability_when_slot_unavailable() -> None:
    session = MagicMock()
    svc = ScheduleImpactService(session)
    change = BlockedPeriodCreateChange(
        staff_id=STAFF_ID,
        starts_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        ends_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
    )
    booking = _operational_booking()
    svc._availability = MagicMock()
    svc._availability.is_occupied_interval_available.return_value = False
    reasons = svc._classify_booking(
        salon_id=SALON_ID,
        change=change,
        overlay=ScheduleOverlay(),
        booking=booking,
        as_of=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
    )
    assert reasons == ("outside_availability",)


def test_overlay_working_hours_create_applied_in_repository() -> None:
    session = MagicMock()
    repo = AvailabilityRepository(session)
    session.scalars.return_value.all.return_value = []
    overlay = ScheduleOverlay(
        working_hours_creates=(
            WorkingHourCreateOverlay(
                staff_id=STAFF_ID,
                day_of_week=0,
                start_time=time(9, 0),
                end_time=time(17, 0),
            ),
        )
    )
    defaults, staff_specific = repo.load_working_hours(
        SALON_ID, STAFF_ID, overlay=overlay
    )
    assert defaults == []
    assert len(staff_specific) == 1
    assert staff_specific[0].start_time == time(9, 0)


def test_overlay_blocked_period_create_applied_in_repository() -> None:
    session = MagicMock()
    repo = AvailabilityRepository(session)
    session.scalars.return_value.all.return_value = []
    block_start = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
    block_end = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    overlay = ScheduleOverlay(
        blocked_period_creates=(
            BlockedPeriodCreateOverlay(
                staff_id=STAFF_ID,
                starts_at=block_start,
                ends_at=block_end,
            ),
        )
    )
    blocks = repo.load_blocked_periods(
        SALON_ID,
        STAFF_ID,
        block_start - timedelta(hours=1),
        block_end + timedelta(hours=1),
        overlay=overlay,
    )
    assert len(blocks) == 1
    assert blocks[0].start == block_start


def test_availability_service_with_overlay_none_delegates_same_as_before() -> None:
    session = MagicMock()
    repo = AvailabilityRepository(session)
    repo.staff_belongs_to_salon = MagicMock(return_value=True)
    repo.get_salon_timezone = MagicMock(return_value="UTC")
    repo.load_working_hours = MagicMock(return_value=([], []))
    repo.load_blocked_periods = MagicMock(return_value=[])
    repo.load_bookings_for_availability = MagicMock(return_value=[])
    svc = AvailabilityService(session)
    svc._repo = repo
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    svc.get_free_gaps(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2026, 7, 2),
        end_date=date(2026, 7, 2),
        service_duration_minutes=60,
        as_of=as_of,
        overlay=None,
    )
    repo.load_working_hours.assert_called_once_with(SALON_ID, STAFF_ID, overlay=None)
    repo.load_blocked_periods.assert_called_once()
    assert repo.load_blocked_periods.call_args.kwargs.get("overlay") is None


def test_build_overlay_working_hours_update_does_not_mutate_loaded_row() -> None:
    wh_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    row = SimpleNamespace(
        id=wh_id,
        staff_id=STAFF_ID,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
        effective_from=None,
        effective_to=None,
        updated_at=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
    )

    session = MagicMock()
    schedule_repo = ScheduleRepository(session)
    schedule_repo.get_working_hour_by_id = MagicMock(return_value=row)
    staff_repo = StaffRepository(session)
    staff_repo.get_staff_by_id = MagicMock(return_value=MagicMock())
    catalog_repo = ServiceCatalogRepository(session)

    change = WorkingHoursUpdateChange(
        working_hours_id=wh_id,
        start_time=time(11, 0),
    )
    build_overlay_from_change(
        salon_id=SALON_ID,
        change=change,
        schedule_repo=schedule_repo,
        staff_repo=staff_repo,
        catalog_repo=catalog_repo,
    )
    assert row.start_time == time(9, 0)


def test_build_overlay_blocked_period_update_does_not_mutate_loaded_row() -> None:
    bp_id = uuid.UUID("22222222-2222-4222-8222-222222222222")
    original_end = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    row = SimpleNamespace(
        id=bp_id,
        staff_id=STAFF_ID,
        starts_at=datetime(2026, 8, 1, 9, 0, tzinfo=UTC),
        ends_at=original_end,
        block_type="manual",
        updated_at=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
    )

    session = MagicMock()
    schedule_repo = ScheduleRepository(session)
    schedule_repo.get_blocked_period_by_id = MagicMock(return_value=row)
    staff_repo = StaffRepository(session)
    staff_repo.get_staff_by_id = MagicMock(return_value=MagicMock())
    catalog_repo = ServiceCatalogRepository(session)

    new_end = datetime(2026, 8, 1, 14, 0, tzinfo=UTC)
    change = BlockedPeriodUpdateChange(
        blocked_period_id=bp_id,
        ends_at=new_end,
    )
    build_overlay_from_change(
        salon_id=SALON_ID,
        change=change,
        schedule_repo=schedule_repo,
        staff_repo=staff_repo,
        catalog_repo=catalog_repo,
    )
    assert row.ends_at == original_end


def test_build_overlay_working_hours_create_affects_all_bookable_staff() -> None:
    session = MagicMock()
    schedule_repo = ScheduleRepository(session)
    staff_repo = StaffRepository(session)
    catalog_repo = ServiceCatalogRepository(session)
    staff_a = MagicMock()
    staff_a.id = STAFF_ID
    staff_b = MagicMock()
    staff_b.id = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    staff_repo.list_staff = MagicMock(return_value=[staff_a, staff_b])
    change = WorkingHoursCreateChange(
        staff_id=None,
        day_of_week=1,
        start_time=time(10, 0),
        end_time=time(18, 0),
    )
    result = build_overlay_from_change(
        salon_id=SALON_ID,
        change=change,
        schedule_repo=schedule_repo,
        staff_repo=staff_repo,
        catalog_repo=catalog_repo,
    )
    assert set(result.affected_staff_ids) == {STAFF_ID, staff_b.id}
