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


def _booking(*, status: str = "pending", expires_at: datetime | None = None) -> Booking:
    if status == "pending" and expires_at is None:
        expires_at = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
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
        expires_at=expires_at,
    )
    booking.id = BOOKING_ID
    return booking


def _service_with_booking(
    booking: Booking | None,
) -> tuple[BookingService, MagicMock, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    svc._repo = repo
    repo.get_booking.return_value = booking

    def _expire_stale(**kwargs: object) -> int:
        if booking is None:
            return 0
        exp = booking.expires_at
        as_of = kwargs.get("as_of")
        if (
            booking.status == "pending"
            and exp is not None
            and as_of is not None
            and exp <= as_of
        ):
            booking.status = "expired"
            return 1
        return 0

    repo.expire_stale_pending_holds.side_effect = _expire_stale
    return svc, session, repo


def test_cancel_pending_success() -> None:
    svc, session, _repo = _service_with_booking(_booking(status="pending"))
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
    svc, _session, _repo = _service_with_booking(_booking(status="confirmed"))
    result = svc.cancel_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        as_of=AS_OF,
    )
    assert result.status == "cancelled"


def test_cancel_missing_booking_not_found() -> None:
    svc, _session, _repo = _service_with_booking(None)
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=AS_OF,
        )


def test_cancel_wrong_token_not_found_no_leak() -> None:
    svc, _session, _repo = _service_with_booking(_booking())
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token="wrong-token",
            as_of=AS_OF,
        )


def test_cancel_terminal_status_rejected() -> None:
    svc, _session, _repo = _service_with_booking(_booking(status="completed"))
    with pytest.raises(BookingValidationError, match="cannot be cancelled"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=AS_OF,
        )


def test_cancel_naive_as_of_rejected() -> None:
    svc, _session, _repo = _service_with_booking(_booking())
    with pytest.raises(BookingValidationError, match="as_of"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=datetime(2026, 6, 1, 12, 0),
        )


def test_admin_cancel_pending_success_without_token() -> None:
    svc, session, _repo = _service_with_booking(_booking(status="pending"))
    result = svc.admin_cancel_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
        reason="admin action",
    )
    assert result.status == "cancelled"
    session.flush.assert_called_once()


def test_admin_cancel_confirmed_success_without_token() -> None:
    svc, _session, _repo = _service_with_booking(_booking(status="confirmed"))
    result = svc.admin_cancel_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )
    assert result.status == "cancelled"


def test_admin_cancel_in_progress_rejected() -> None:
    svc, _session, _repo = _service_with_booking(_booking(status="in_progress"))
    with pytest.raises(BookingValidationError, match="cannot be cancelled"):
        svc.admin_cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


def test_cancel_stale_pending_expires_then_rejected() -> None:
    stale_expires = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
    booking = _booking(status="pending", expires_at=stale_expires)
    svc, _session, repo = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="cannot be cancelled"):
        svc.cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            as_of=AS_OF,
        )
    assert booking.status == "expired"
    repo.expire_stale_pending_holds.assert_called_once()


def test_admin_cancel_stale_pending_expires_then_rejected() -> None:
    stale_expires = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
    booking = _booking(status="pending", expires_at=stale_expires)
    svc, _session, _repo = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="cannot be cancelled"):
        svc.admin_cancel_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )
    assert booking.status == "expired"
