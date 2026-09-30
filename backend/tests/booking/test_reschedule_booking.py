from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.booking.errors import (
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)
from app.services.booking.manage_token import hash_manage_token
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
STAFF_A = uuid.uuid4()
STAFF_B = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
OLD_START = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
NEW_START = datetime(2026, 6, 3, 14, 0, tzinfo=UTC)
RAW_TOKEN = "valid-manage-token-for-reschedule-unit"
PEPPER = get_settings().booking_manage_token_pepper


def _booking(*, status: str = "pending", staff_id: uuid.UUID = STAFF_A) -> Booking:
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=uuid.uuid4(),
        staff_id=staff_id,
        service_id=SERVICE_ID,
        starts_at=OLD_START,
        ends_at=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
        status=status,
        source="public",
        price_cents=1000,
        currency_code="KZT",
        duration_minutes=60,
        manage_token_hash=hash_manage_token(RAW_TOKEN, pepper=PEPPER),
    )
    booking.id = BOOKING_ID
    return booking


def _active_staff(staff_id: uuid.UUID = STAFF_B) -> Staff:
    staff = Staff(
        salon_id=SALON_ID,
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    staff.id = staff_id
    return staff


def _active_service() -> Service:
    service = Service(
        salon_id=SALON_ID,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )
    service.id = SERVICE_ID
    return service


def _service_with_booking(
    booking: Booking | None,
) -> tuple[BookingService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    availability = MagicMock()
    svc._repo = repo
    svc._availability = availability
    repo.get_booking.return_value = booking
    repo.get_staff.return_value = _active_staff()
    repo.get_service.return_value = _active_service()
    repo.staff_performs_service.return_value = True
    availability.is_occupied_interval_available.return_value = True
    return svc, session, repo, availability


def test_reschedule_pending_success() -> None:
    booking = _booking(status="pending")
    svc, session, repo, availability = _service_with_booking(booking)
    result = svc.reschedule_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        new_staff_id=STAFF_B,
        new_service_start=NEW_START,
        as_of=AS_OF,
    )
    assert result.booking_id == BOOKING_ID
    assert result.status == "pending"
    assert result.staff_id == STAFF_B
    assert result.service_start == NEW_START
    assert result.service_end == datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
    assert booking.staff_id == STAFF_B
    assert booking.starts_at == NEW_START
    assert booking.ends_at == datetime(2026, 6, 3, 15, 0, tzinfo=UTC)
    repo.expire_stale_pending_holds.assert_called_once()
    availability.is_occupied_interval_available.assert_called_once()
    kwargs = availability.is_occupied_interval_available.call_args.kwargs
    assert kwargs["exclude_booking_id"] == BOOKING_ID
    session.flush.assert_called_once()


def test_reschedule_confirmed_success() -> None:
    booking = _booking(status="confirmed")
    svc, _session, _repo, _availability = _service_with_booking(booking)
    result = svc.reschedule_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        new_staff_id=STAFF_A,
        new_service_start=NEW_START,
        as_of=AS_OF,
    )
    assert result.status == "confirmed"


def test_reschedule_missing_booking_not_found() -> None:
    svc, _session, _repo, _availability = _service_with_booking(None)
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_reschedule_wrong_token_not_found_no_leak() -> None:
    svc, _session, _repo, _availability = _service_with_booking(_booking())
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token="wrong-token",
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_reschedule_terminal_status_rejected() -> None:
    svc, _session, _repo, _availability = _service_with_booking(
        _booking(status="cancelled")
    )
    with pytest.raises(BookingValidationError, match="cannot be rescheduled"):
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_reschedule_slot_unavailable() -> None:
    svc, _session, _repo, availability = _service_with_booking(_booking())
    availability.is_occupied_interval_available.return_value = False
    with pytest.raises(SlotNotAvailableError):
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_reschedule_flush_integrity_error_becomes_overlap() -> None:
    booking = _booking()
    svc, session, _repo, _availability = _service_with_booking(booking)
    session.flush.side_effect = IntegrityError("stmt", {}, Exception("overlap"))
    with pytest.raises(BookingOverlapError):
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_reschedule_naive_as_of_rejected() -> None:
    svc, _session, _repo, _availability = _service_with_booking(_booking())
    with pytest.raises(BookingValidationError, match="as_of"):
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=datetime(2026, 6, 1, 12, 0),
        )


def test_admin_reschedule_pending_success_without_token() -> None:
    booking = _booking(status="pending")
    svc, session, _repo, availability = _service_with_booking(booking)
    result = svc.admin_reschedule_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        new_staff_id=STAFF_B,
        new_service_start=NEW_START,
        as_of=AS_OF,
    )
    assert result.status == "pending"
    availability.is_occupied_interval_available.assert_called_once()
    session.flush.assert_called_once()


def test_admin_reschedule_confirmed_success_without_token() -> None:
    svc, _session, _repo, _availability = _service_with_booking(
        _booking(status="confirmed")
    )
    result = svc.admin_reschedule_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        new_staff_id=STAFF_B,
        new_service_start=NEW_START,
        as_of=AS_OF,
    )
    assert result.status == "confirmed"


def test_admin_reschedule_in_progress_rejected() -> None:
    svc, _session, _repo, _availability = _service_with_booking(
        _booking(status="in_progress")
    )
    with pytest.raises(BookingValidationError, match="cannot be rescheduled"):
        svc.admin_reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_admin_reschedule_slot_unavailable() -> None:
    svc, _session, _repo, availability = _service_with_booking(_booking())
    availability.is_occupied_interval_available.return_value = False
    with pytest.raises(SlotNotAvailableError):
        svc.admin_reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )


def test_admin_reschedule_flush_integrity_error_becomes_overlap() -> None:
    svc, session, _repo, _availability = _service_with_booking(_booking())
    session.flush.side_effect = IntegrityError("stmt", {}, Exception("overlap"))
    with pytest.raises(BookingOverlapError):
        svc.admin_reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            new_staff_id=STAFF_B,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )
