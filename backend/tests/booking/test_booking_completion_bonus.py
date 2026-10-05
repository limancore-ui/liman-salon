"""Unit tests: booking completion triggers bonus earn (C20.2.2)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.db.models.booking import Booking
from app.services.bonus.errors import BonusLedgerValidationError
from app.services.bonus.service import BonusLedgerService
from app.services.booking.errors import BookingValidationError
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _booking(*, status: str = "confirmed", price_cents: int = 1000) -> Booking:
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        starts_at=datetime(2026, 6, 2, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
        status=status,
        source="admin",
        price_cents=price_cents,
        currency_code="KZT",
        duration_minutes=60,
    )
    booking.id = BOOKING_ID
    return booking


def _service_with_booking(
    booking: Booking | None,
    *,
    bonus_ledger: BonusLedgerService | MagicMock | None = None,
) -> tuple[BookingService, MagicMock]:
    session = MagicMock()
    svc = BookingService(session, bonus_ledger=bonus_ledger)
    repo = MagicMock()
    svc._repo = repo
    repo.get_booking.return_value = booking
    repo.expire_stale_pending_holds.return_value = 0
    return svc, session


def test_confirmed_to_completed_calls_earn_once() -> None:
    booking = _booking(status="confirmed")
    mock_bonus = MagicMock(spec=BonusLedgerService)
    svc, _session = _service_with_booking(booking, bonus_ledger=mock_bonus)

    result = svc.admin_complete_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )

    assert result.status == "completed"
    mock_bonus.earn_for_booking.assert_called_once_with(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
    )


def test_in_progress_to_completed_calls_earn_once() -> None:
    booking = _booking(status="in_progress")
    mock_bonus = MagicMock(spec=BonusLedgerService)
    svc, _session = _service_with_booking(booking, bonus_ledger=mock_bonus)

    svc.admin_complete_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )

    mock_bonus.earn_for_booking.assert_called_once()


def test_complete_without_bonus_ledger_skips_earn() -> None:
    booking = _booking(status="confirmed")
    svc, _session = _service_with_booking(booking, bonus_ledger=None)

    svc.admin_complete_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )

    assert booking.status == "completed"


def test_repeat_complete_does_not_call_earn_twice() -> None:
    booking = _booking(status="confirmed")
    mock_bonus = MagicMock(spec=BonusLedgerService)
    svc, _session = _service_with_booking(booking, bonus_ledger=mock_bonus)

    svc.admin_complete_visit(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        as_of=AS_OF,
    )

    with pytest.raises(BookingValidationError, match="cannot be completed"):
        svc.admin_complete_visit(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )

    mock_bonus.earn_for_booking.assert_called_once()


def test_ledger_failure_propagates_from_complete() -> None:
    booking = _booking(status="confirmed")
    mock_bonus = MagicMock(spec=BonusLedgerService)
    mock_bonus.earn_for_booking.side_effect = BonusLedgerValidationError(
        "bonus ledger write failed"
    )
    svc, _session = _service_with_booking(booking, bonus_ledger=mock_bonus)

    with pytest.raises(BonusLedgerValidationError, match="bonus ledger write failed"):
        svc.admin_complete_visit(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            as_of=AS_OF,
        )

    mock_bonus.earn_for_booking.assert_called_once()
