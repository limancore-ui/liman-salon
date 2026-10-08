from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.services.availability.intervals import (
    DEFAULT_SERVICE_SLOT_STEP_MINUTES,
    net_service_slots_from_free_gaps,
)
from app.services.availability.service import AvailabilityService
from app.services.availability.types import (
    BookingOccupancy,
    BusyInterval,
    ServiceForAvailability,
    TimeInterval,
    WorkingHourSpec,
)

UTC = timezone.utc
SALON_ID = uuid.uuid4()
STAFF_A = uuid.uuid4()
STAFF_B = uuid.uuid4()
SERVICE_ID = uuid.uuid4()


def test_discrete_starts_10_to_19_sixty_minute_service() -> None:
    gaps = [
        TimeInterval(
            start=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
            end=datetime(2025, 6, 2, 19, 0, tzinfo=UTC),
        )
    ]
    slots = net_service_slots_from_free_gaps(
        gaps,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        slot_step_minutes=30,
        tz=ZoneInfo("UTC"),
    )
    starts = [s.service_start for s in slots]
    assert starts == [
        datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 10, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 11, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 12, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 13, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 13, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 14, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 14, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 15, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 15, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 16, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 16, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 17, 0, tzinfo=UTC),
        datetime(2025, 6, 2, 17, 30, tzinfo=UTC),
        datetime(2025, 6, 2, 18, 0, tzinfo=UTC),
    ]
    assert slots[-1].service_end == datetime(2025, 6, 2, 19, 0, tzinfo=UTC)


def test_duration_prevents_invalid_final_start() -> None:
    gaps = [
        TimeInterval(
            start=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
            end=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
        )
    ]
    slots = net_service_slots_from_free_gaps(
        gaps,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        tz=ZoneInfo("UTC"),
    )
    assert [s.service_start for s in slots] == [
        datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
    ]


def test_buffers_respected_on_discrete_grid() -> None:
    gaps = [
        TimeInterval(
            start=datetime(2025, 6, 2, 9, 0, tzinfo=UTC),
            end=datetime(2025, 6, 2, 17, 0, tzinfo=UTC),
        )
    ]
    slots = net_service_slots_from_free_gaps(
        gaps,
        duration_minutes=60,
        buffer_before_minutes=15,
        buffer_after_minutes=15,
        tz=ZoneInfo("UTC"),
    )
    assert slots[0].service_start == datetime(2025, 6, 2, 9, 30, tzinfo=UTC)
    assert slots[-1].service_start == datetime(2025, 6, 2, 15, 30, tzinfo=UTC)


def _service_with_repo(repo: MagicMock) -> AvailabilityService:
    session = MagicMock()
    svc = AvailabilityService(session)
    svc._repo = repo
    return svc


def _base_repo() -> MagicMock:
    repo = MagicMock()
    repo.get_salon_timezone.return_value = "UTC"
    repo.load_working_hours.return_value = (
        [
            WorkingHourSpec(
                day_of_week=0,
                start_time=time(9, 0),
                end_time=time(17, 0),
                staff_id=None,
                effective_from=None,
                effective_to=None,
            )
        ],
        [],
    )
    repo.load_blocked_periods.return_value = []
    repo.load_bookings_for_availability.return_value = []
    repo.staff_belongs_to_salon.return_value = True
    return repo


def _active_service(**kwargs: object) -> ServiceForAvailability:
    defaults = {
        "id": SERVICE_ID,
        "is_active": True,
        "duration_minutes": 60,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
    }
    defaults.update(kwargs)
    return ServiceForAvailability(**defaults)  # type: ignore[arg-type]


def test_existing_booking_removes_starts() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.staff_eligible_for_service.return_value = True
    repo.load_bookings_for_availability.return_value = [
        BookingOccupancy(
            starts_at=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
            ends_at=datetime(2025, 6, 2, 13, 0, tzinfo=UTC),
            status="confirmed",
            expires_at=None,
        )
    ]
    svc = _service_with_repo(repo)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        staff_id=STAFF_A,
        as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    starts = {s.service_start for s in result.staff[0].slots}
    assert datetime(2025, 6, 2, 12, 0, tzinfo=UTC) not in starts
    assert datetime(2025, 6, 2, 11, 0, tzinfo=UTC) in starts


def test_blocked_period_removes_starts() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.list_bookable_staff_for_service.return_value = [STAFF_A]
    repo.load_blocked_periods.return_value = [
        BusyInterval(
            start=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
            end=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
        )
    ]
    svc = _service_with_repo(repo)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    starts = {s.service_start for s in result.staff[0].slots}
    assert datetime(2025, 6, 2, 10, 0, tzinfo=UTC) not in starts
    assert datetime(2025, 6, 2, 12, 0, tzinfo=UTC) in starts


def test_today_between_grid_points_clips_elapsed_starts() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.staff_eligible_for_service.return_value = True
    svc = _service_with_repo(repo)
    as_of = datetime(2025, 6, 2, 16, 55, tzinfo=UTC)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        staff_id=STAFF_A,
        as_of=as_of,
    )
    starts = {s.service_start for s in result.staff[0].slots}
    assert datetime(2025, 6, 2, 16, 30, tzinfo=UTC) not in starts


def test_today_clips_elapsed_starts_salon_timezone() -> None:
    repo = _base_repo()
    repo.get_salon_timezone.return_value = "UTC"
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.staff_eligible_for_service.return_value = True
    svc = _service_with_repo(repo)
    as_of = datetime(2025, 6, 2, 16, 55, tzinfo=UTC)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        staff_id=STAFF_A,
        as_of=as_of,
    )
    starts = [s.service_start for s in result.staff[0].slots]
    assert datetime(2025, 6, 2, 16, 0, tzinfo=UTC) not in starts
    assert datetime(2025, 6, 2, 16, 30, tzinfo=UTC) not in starts
    assert datetime(2025, 6, 2, 16, 0, tzinfo=UTC) not in starts


def test_past_date_returns_no_starts() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.staff_eligible_for_service.return_value = True
    svc = _service_with_repo(repo)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 1),
        end_date=date(2025, 6, 1),
        staff_id=STAFF_A,
        as_of=datetime(2025, 6, 2, 10, 0, tzinfo=UTC),
    )
    assert result.staff[0].slots == ()


def test_future_date_unfiltered_by_as_of() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.staff_eligible_for_service.return_value = True
    svc = _service_with_repo(repo)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 9),
        end_date=date(2025, 6, 9),
        staff_id=STAFF_A,
        as_of=datetime(2025, 6, 2, 16, 55, tzinfo=UTC),
    )
    assert len(result.staff[0].slots) > 1


def test_any_staff_returns_per_staff_slots() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.list_bookable_staff_for_service.return_value = [STAFF_A, STAFF_B]
    svc = _service_with_repo(repo)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    assert len(result.staff) == 2
    assert len(result.staff[0].slots) == len(result.staff[1].slots)


def test_specific_staff_only_that_staff() -> None:
    repo = _base_repo()
    repo.get_service_for_availability.return_value = _active_service(duration_minutes=60)
    repo.staff_eligible_for_service.return_value = True
    repo.list_bookable_staff_for_service.return_value = [STAFF_A, STAFF_B]
    svc = _service_with_repo(repo)
    result = svc.get_service_availability(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        staff_id=STAFF_A,
        as_of=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
    )
    assert len(result.staff) == 1
    assert result.staff[0].staff_id == STAFF_A


def test_default_step_is_thirty_minutes() -> None:
    assert DEFAULT_SERVICE_SLOT_STEP_MINUTES == 30
