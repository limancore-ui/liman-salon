from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone
from unittest.mock import MagicMock

from app.services.availability.service import AvailabilityService
from app.services.availability.types import BookingOccupancy, BusyInterval, WorkingHourSpec

UTC = timezone.utc
SALON_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)


def _service_with_repo(repo: MagicMock) -> AvailabilityService:
    session = MagicMock()
    svc = AvailabilityService(session)
    svc._repo = repo
    return svc


def _base_repo() -> MagicMock:
    repo = MagicMock()
    repo.staff_belongs_to_salon.return_value = True
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
    return repo


def test_free_period_full_working_day() -> None:
    repo = _base_repo()
    svc = _service_with_repo(repo)
    gaps = svc.get_free_gaps(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        service_duration_minutes=30,
        as_of=AS_OF,
    )
    assert len(gaps) == 1
    assert gaps[0].start == datetime(2025, 6, 2, 9, 0, tzinfo=UTC)
    assert gaps[0].end == datetime(2025, 6, 2, 17, 0, tzinfo=UTC)
    repo.load_working_hours.assert_called_once_with(SALON_ID, STAFF_ID)


def test_blocked_period_reduces_gaps() -> None:
    repo = _base_repo()
    repo.load_blocked_periods.return_value = [
        BusyInterval(
            start=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
            end=datetime(2025, 6, 2, 13, 0, tzinfo=UTC),
        )
    ]
    svc = _service_with_repo(repo)
    gaps = svc.get_free_gaps(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        service_duration_minutes=30,
        as_of=AS_OF,
    )
    assert len(gaps) == 2


def test_confirmed_booking_in_sql_path_via_repo() -> None:
    repo = _base_repo()
    repo.load_bookings_for_availability.return_value = [
        BookingOccupancy(
            starts_at=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
            ends_at=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
            status="confirmed",
            expires_at=None,
        )
    ]
    svc = _service_with_repo(repo)
    gaps = svc.get_free_gaps(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        service_duration_minutes=30,
        as_of=AS_OF,
    )
    repo.load_bookings_for_availability.assert_called_once()
    args, kwargs = repo.load_bookings_for_availability.call_args
    assert kwargs.get("salon_id", args[0] if args else None) == SALON_ID
    assert kwargs.get("staff_id", args[1] if len(args) > 1 else None) == STAFF_ID
    assert kwargs.get("as_of", args[4] if len(args) > 4 else None) == AS_OF
    assert len(gaps) == 2


def test_stale_pending_from_repo_does_not_subtract_twice_guard() -> None:
    """If a stale pending row were returned, pure rule must not treat it as busy."""
    repo = _base_repo()
    repo.load_bookings_for_availability.return_value = [
        BookingOccupancy(
            starts_at=datetime(2025, 6, 2, 11, 0, tzinfo=UTC),
            ends_at=datetime(2025, 6, 2, 12, 0, tzinfo=UTC),
            status="pending",
            expires_at=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        )
    ]
    svc = _service_with_repo(repo)
    gaps = svc.get_free_gaps(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        service_duration_minutes=30,
        as_of=AS_OF,
    )
    assert len(gaps) == 1


def test_tenant_scoping_empty_when_staff_not_in_salon() -> None:
    repo = _base_repo()
    repo.staff_belongs_to_salon.return_value = False
    svc = _service_with_repo(repo)
    gaps = svc.get_free_gaps(
        salon_id=SALON_ID,
        staff_id=STAFF_ID,
        start_date=date(2025, 6, 2),
        end_date=date(2025, 6, 2),
        service_duration_minutes=30,
        as_of=AS_OF,
    )
    assert gaps == []
    repo.load_working_hours.assert_not_called()
