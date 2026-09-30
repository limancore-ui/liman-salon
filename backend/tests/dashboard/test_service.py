from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.booking.types import BookingUpcomingRow
from app.services.dashboard.errors import DashboardValidationError
from app.services.dashboard.service import DashboardService

SALON_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
AS_OF = datetime(2026, 9, 25, 6, 0, tzinfo=timezone.utc)


def _service_with_mocks() -> tuple[DashboardService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    svc = DashboardService(session)
    booking_repo = MagicMock()
    staff_repo = MagicMock()
    salon_repo = MagicMock()
    svc._booking_repo = booking_repo
    svc._staff_repo = staff_repo
    svc._salon_repo = salon_repo
    return svc, booking_repo, staff_repo, salon_repo


def test_snapshot_aggregates_counts_and_staff() -> None:
    svc, booking_repo, staff_repo, salon_repo = _service_with_mocks()
    salon_repo.get_salon_timezone.return_value = "UTC"
    booking_repo.count_bookings_starts_in_range.return_value = 5
    booking_repo.status_counts_starts_in_range.return_value = {
        "confirmed": 3,
        "cancelled": 2,
    }
    booking_repo.list_upcoming_bookings_starts_in_range.return_value = []
    staff_repo.count_active_staff.return_value = 4
    staff_repo.list_staff.return_value = [MagicMock()]

    snap = svc.get_admin_snapshot(salon_id=SALON_ID, as_of=AS_OF)

    assert snap.salon_date == date(2026, 9, 25)
    assert snap.today_booking_count == 5
    assert snap.status_counts.confirmed == 3
    assert snap.status_counts.cancelled == 2
    assert snap.status_counts.pending == 0
    assert snap.active_staff_count == 4
    booking_repo.count_bookings_starts_in_range.assert_called_once()
    assert booking_repo.count_bookings_starts_in_range.call_args.kwargs["salon_id"] == SALON_ID


def test_snapshot_naive_as_of_rejected() -> None:
    svc, _, _, _ = _service_with_mocks()
    with pytest.raises(DashboardValidationError):
        svc.get_admin_snapshot(
            salon_id=SALON_ID,
            as_of=datetime(2026, 9, 25, 6, 0),
        )


def test_snapshot_no_active_staff_warning() -> None:
    svc, booking_repo, staff_repo, salon_repo = _service_with_mocks()
    salon_repo.get_salon_timezone.return_value = "UTC"
    booking_repo.count_bookings_starts_in_range.return_value = 0
    booking_repo.status_counts_starts_in_range.return_value = {}
    booking_repo.list_upcoming_bookings_starts_in_range.return_value = []
    staff_repo.count_active_staff.return_value = 0

    snap = svc.get_admin_snapshot(salon_id=SALON_ID, as_of=AS_OF)

    codes = [w.code for w in snap.warnings]
    assert "no_active_staff" in codes
    staff_repo.list_staff.assert_not_called()


def test_snapshot_maps_upcoming_from_booking_rows() -> None:
    svc, booking_repo, staff_repo, salon_repo = _service_with_mocks()
    salon_repo.get_salon_timezone.return_value = "UTC"
    booking_repo.count_bookings_starts_in_range.return_value = 1
    booking_repo.status_counts_starts_in_range.return_value = {"confirmed": 1}
    row = BookingUpcomingRow(
        id=uuid.uuid4(),
        starts_at=datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 25, 13, 0, tzinfo=timezone.utc),
        customer_name="A",
        customer_phone=None,
        service_name="S",
        staff_name="T",
        status="confirmed",
        price_cents=100,
    )
    booking_repo.list_upcoming_bookings_starts_in_range.return_value = [row]
    staff_repo.count_active_staff.return_value = 1
    staff_repo.list_staff.return_value = [MagicMock()]

    snap = svc.get_admin_snapshot(salon_id=SALON_ID, as_of=AS_OF)

    assert len(snap.upcoming_bookings) == 1
    assert snap.upcoming_bookings[0].customer_name == "A"
    booking_repo.list_upcoming_bookings_starts_in_range.assert_called_once()
    kwargs = booking_repo.list_upcoming_bookings_starts_in_range.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["as_of"] == AS_OF
