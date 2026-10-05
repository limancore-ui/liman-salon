from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.db.models.booking import Booking
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _booking(*, status: str = "confirmed") -> Booking:
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        starts_at=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
        status=status,
        source="admin",
        price_cents=1000,
        currency_code="KZT",
        duration_minutes=60,
    )
    booking.id = BOOKING_ID
    if status == "confirmed":
        booking.confirmed_at = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
    return booking


def _service_with_booking(
    booking: Booking | None,
) -> tuple[BookingService, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    svc._repo = repo
    repo.get_booking.return_value = booking
    repo.expire_stale_pending_holds.return_value = 0
    return svc, session


def test_admin_start_visit_from_confirmed_success() -> None:
    booking = _booking(status="confirmed")
    svc, session = _service_with_booking(booking)
    result = svc.admin_start_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )
    assert result.booking_id == BOOKING_ID
    assert result.status == "in_progress"
    assert booking.status == "in_progress"
    session.flush.assert_called()


@pytest.mark.parametrize(
    "status",
    ["pending", "in_progress", "completed", "cancelled", "no_show", "expired"],
)
def test_admin_start_visit_illegal_status_rejected(status: str) -> None:
    booking = _booking(status=status)
    if status == "pending":
        booking.expires_at = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    svc, _session = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="cannot be started"):
        svc.admin_start_visit(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


def test_admin_complete_visit_from_in_progress_sets_completed_at() -> None:
    booking = _booking(status="in_progress")
    svc, session = _service_with_booking(booking)
    result = svc.admin_complete_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )
    assert result.status == "completed"
    assert result.completed_at == AS_OF
    assert booking.completed_at == AS_OF
    session.flush.assert_called()


def test_admin_complete_visit_from_confirmed_sets_completed_at() -> None:
    booking = _booking(status="confirmed")
    svc, session = _service_with_booking(booking)
    result = svc.admin_complete_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )
    assert result.status == "completed"
    assert result.completed_at == AS_OF
    assert booking.status == "completed"
    session.flush.assert_called()


@pytest.mark.parametrize(
    "status",
    ["pending", "completed", "cancelled", "no_show", "expired"],
)
def test_admin_complete_visit_illegal_status_rejected(status: str) -> None:
    booking = _booking(status=status)
    svc, _session = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="cannot be completed"):
        svc.admin_complete_visit(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


def test_admin_no_show_from_confirmed_success() -> None:
    booking = _booking(status="confirmed")
    svc, session = _service_with_booking(booking)
    result = svc.admin_mark_no_show(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )
    assert result.status == "no_show"
    assert booking.status == "no_show"
    session.flush.assert_called()


def test_admin_no_show_from_in_progress_rejected() -> None:
    booking = _booking(status="in_progress")
    svc, _session = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="no-show"):
        svc.admin_mark_no_show(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


@pytest.mark.parametrize(
    "status",
    ["pending", "in_progress", "completed", "cancelled", "no_show", "expired"],
)
def test_admin_no_show_illegal_status_rejected(status: str) -> None:
    booking = _booking(status=status)
    svc, _session = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="no-show"):
        svc.admin_mark_no_show(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


def test_admin_start_visit_missing_booking_not_found() -> None:
    svc, _session = _service_with_booking(None)
    with pytest.raises(BookingNotFoundError):
        svc.admin_start_visit(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


def test_admin_visit_naive_as_of_rejected() -> None:
    booking = _booking(status="confirmed")
    svc, _session = _service_with_booking(booking)
    naive = datetime(2026, 6, 1, 12, 0)
    with pytest.raises(BookingValidationError, match="timezone-aware"):
        svc.admin_start_visit(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=naive,
        )
