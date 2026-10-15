from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.db.models.booking import Booking
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.booking.errors import BookingNotFoundError
from app.services.booking.manage_token import hash_manage_token
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
RAW_TOKEN = "valid-manage-token-for-read-unit"
PEPPER = get_settings().booking_manage_token_pepper
TZ = "Asia/Almaty"


def _booking(*, status: str = "pending", expires_at: datetime | None = None) -> Booking:
    if status == "pending" and expires_at is None:
        expires_at = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=uuid.uuid4(),
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        starts_at=datetime(2026, 6, 2, 9, 0, tzinfo=UTC),
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


def _service() -> Service:
    return Service(
        salon_id=SALON_ID,
        name="Haircut",
        duration_minutes=60,
        buffer_before_minutes=15,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )


def _staff() -> Staff:
    return Staff(
        salon_id=SALON_ID,
        display_name="Alex",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )


def _service_with_booking(
    booking: Booking | None,
) -> tuple[BookingService, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    svc._repo = repo
    repo.get_booking.return_value = booking
    repo.get_service.return_value = _service()
    repo.get_staff.return_value = _staff()
    return svc, repo


def test_get_manage_success_pending() -> None:
    svc, _repo = _service_with_booking(_booking(status="pending"))
    result = svc.get_public_booking_for_manage(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        salon_timezone=TZ,
        as_of=AS_OF,
    )
    assert result.booking_id == BOOKING_ID
    assert result.status == "pending"
    assert result.service_id == SERVICE_ID
    assert result.service_name == "Haircut"
    assert result.staff_display_name == "Alex"
    assert result.service_start == datetime(2026, 6, 2, 9, 15, tzinfo=UTC)
    assert result.service_end == datetime(2026, 6, 2, 10, 15, tzinfo=UTC)
    assert result.can_cancel is True
    assert result.can_reschedule is True
    assert result.timezone == TZ
    assert result.hold_expires_at is not None


def test_get_manage_stale_pending_reports_expired_without_db_write() -> None:
    booking = _booking(
        status="pending",
        expires_at=datetime(2026, 5, 31, 12, 0, tzinfo=UTC),
    )
    svc, repo = _service_with_booking(booking)
    result = svc.get_public_booking_for_manage(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        token=RAW_TOKEN,
        salon_timezone=TZ,
        as_of=AS_OF,
    )
    assert result.status == "expired"
    assert result.can_cancel is False
    assert result.can_reschedule is False
    assert booking.status == "pending"
    repo.expire_stale_pending_holds.assert_not_called()


def test_get_manage_missing_token() -> None:
    svc, _repo = _service_with_booking(_booking())
    with pytest.raises(BookingNotFoundError):
        svc.get_public_booking_for_manage(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=None,
            salon_timezone=TZ,
            as_of=AS_OF,
        )


def test_get_manage_invalid_token() -> None:
    svc, _repo = _service_with_booking(_booking())
    with pytest.raises(BookingNotFoundError):
        svc.get_public_booking_for_manage(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token="wrong-token",
            salon_timezone=TZ,
            as_of=AS_OF,
        )


def test_get_manage_missing_booking() -> None:
    svc, _repo = _service_with_booking(None)
    with pytest.raises(BookingNotFoundError):
        svc.get_public_booking_for_manage(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            salon_timezone=TZ,
            as_of=AS_OF,
        )
