from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.db.models.booking import Booking
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.manage_token import hash_manage_token
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
RAW_TOKEN = "valid-manage-token-for-unit-test"
PEPPER = get_settings().booking_manage_token_pepper


def _booking(*, status: str = "pending") -> Booking:
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=uuid.uuid4(),
        staff_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        starts_at=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
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


def _service_with_booking(booking: Booking | None) -> tuple[BookingService, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    svc._repo = repo
    repo.get_booking.return_value = booking
    return svc, session


def test_cancel_pending_success() -> None:
    svc, session = _service_with_booking(_booking(status="pending"))
    result = svc.cancel_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        as_of=AS_OF,
        reason="changed plans",
    )
    assert result.booking_id == BOOKING_ID
    assert result.status == "cancelled"
    assert result.cancelled_at == AS_OF
    booking = svc._repo.get_booking.return_value
    assert booking.status == "cancelled"
    assert booking.cancellation_reason == "changed plans"
    session.flush.assert_called_once()


def test_cancel_confirmed_success() -> None:
    svc, _session = _service_with_booking(_booking(status="confirmed"))
    result = svc.cancel_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        as_of=AS_OF,
    )
    assert result.status == "cancelled"


def test_cancel_missing_booking_not_found() -> None:
    svc, _session = _service_with_booking(None)
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=AS_OF,
        )


def test_cancel_wrong_token_not_found_no_leak() -> None:
    svc, _session = _service_with_booking(_booking())
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token="wrong-token",
            as_of=AS_OF,
        )


def test_cancel_terminal_status_rejected() -> None:
    svc, _session = _service_with_booking(_booking(status="completed"))
    with pytest.raises(BookingValidationError, match="cannot be cancelled"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=AS_OF,
        )


def test_cancel_naive_as_of_rejected() -> None:
    svc, _session = _service_with_booking(_booking())
    with pytest.raises(BookingValidationError, match="as_of"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=datetime(2026, 6, 1, 12, 0),
        )
