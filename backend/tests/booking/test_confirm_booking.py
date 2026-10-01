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


def _booking(
    *,
    status: str = "pending",
    expires_at: datetime | None = None,
) -> Booking:
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


def test_admin_confirm_active_pending_success() -> None:
    booking = _booking(status="pending")
    svc, session, _repo = _service_with_booking(booking)
    result = svc.admin_confirm_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )
    assert result.booking_id == BOOKING_ID
    assert result.status == "confirmed"
    assert result.confirmed_at == AS_OF
    assert booking.status == "confirmed"
    assert booking.confirmed_at == AS_OF
    assert booking.expires_at is None
    session.flush.assert_called_once()


def test_admin_confirm_stale_pending_expires_then_rejected() -> None:
    stale_expires = datetime(2026, 6, 1, 11, 0, tzinfo=UTC)
    booking = _booking(status="pending", expires_at=stale_expires)
    svc, _session, repo = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="cannot be confirmed"):
        svc.admin_confirm_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )
    assert booking.status == "expired"
    repo.expire_stale_pending_holds.assert_called_once()


def test_admin_confirm_pending_null_expires_at_rejected() -> None:
    booking = _booking(status="pending", expires_at=None)
    booking.expires_at = None
    svc, session, _repo = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="requires expires_at"):
        svc.admin_confirm_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )
    assert booking.status == "pending"
    assert booking.expires_at is None
    session.flush.assert_not_called()


@pytest.mark.parametrize(
    "status",
    ["confirmed", "cancelled", "in_progress", "completed", "no_show", "expired"],
)
def test_admin_confirm_non_pending_rejected(status: str) -> None:
    expires = datetime(2026, 6, 2, 12, 0, tzinfo=UTC) if status == "pending" else None
    booking = _booking(status=status, expires_at=expires)
    svc, session, _repo = _service_with_booking(booking)
    with pytest.raises(BookingValidationError, match="cannot be confirmed"):
        svc.admin_confirm_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )
    session.flush.assert_not_called()


def test_admin_confirm_missing_booking_not_found() -> None:
    svc, _session, _repo = _service_with_booking(None)
    with pytest.raises(BookingNotFoundError, match="booking not found"):
        svc.admin_confirm_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )


def test_admin_confirm_naive_as_of_rejected() -> None:
    svc, _session, _repo = _service_with_booking(_booking(status="pending"))
    with pytest.raises(BookingValidationError, match="as_of"):
        svc.admin_confirm_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=datetime(2026, 6, 1, 12, 0),
        )
