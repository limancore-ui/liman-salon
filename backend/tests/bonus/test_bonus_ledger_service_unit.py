from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.booking import Booking
from app.db.models.bonus_transaction import BonusTransaction
from app.db.models.customer import Customer
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.bonus.errors import BonusLedgerValidationError
from app.services.bonus.service import BonusLedgerService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()


def _booking(*, status: str = "completed", price_cents: int = 10_000) -> Booking:
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        starts_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 9, 1, 11, 0, tzinfo=UTC),
        status=status,
        price_cents=price_cents,
        currency_code="KZT",
        duration_minutes=60,
    )
    booking.id = BOOKING_ID
    return booking


def _customer(*, bonus_balance_cents: int = 0) -> Customer:
    customer = Customer(
        salon_id=SALON_ID,
        full_name="Guest",
        phone="+77001234567",
        bonus_balance_cents=bonus_balance_cents,
    )
    customer.id = CUSTOMER_ID
    return customer


def _ledger_svc(
    *,
    booking: Booking | None,
    salon_settings: dict | None = None,
) -> tuple[BonusLedgerService, MagicMock, MagicMock, MagicMock]:
    session = MagicMock()
    svc = BonusLedgerService(session)
    bookings = MagicMock()
    repo = MagicMock()
    svc._bookings = bookings
    svc._repo = repo

    bookings.get_booking.return_value = booking
    bookings.get_salon_settings.return_value = salon_settings or {
        "v": 1,
        "bonuses": {"enabled": True, "earn_percentage": 10},
    }
    return svc, session, bookings, repo


def test_earn_disabled_policy_is_no_op() -> None:
    booking = _booking()
    svc, _session, bookings, repo = _ledger_svc(
        booking=booking,
        salon_settings={"v": 1, "bonuses": {"enabled": False, "earn_percentage": 10}},
    )

    result = svc.earn_for_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
    )

    assert result is None
    repo.get_customer_for_update.assert_not_called()
    bookings.get_salon_settings.assert_called_once_with(SALON_ID)


@pytest.mark.parametrize(
    "status",
    ["pending", "confirmed", "in_progress", "cancelled", "no_show", "expired"],
)
def test_earn_rejects_non_completed_booking(status: str) -> None:
    svc, _session, _bookings, repo = _ledger_svc(booking=_booking(status=status))

    with pytest.raises(BookingValidationError, match="cannot be earned"):
        svc.earn_for_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            customer_id=CUSTOMER_ID,
        )

    repo.get_customer_for_update.assert_not_called()


def test_earn_booking_not_found() -> None:
    svc, _session, _bookings, repo = _ledger_svc(booking=None)

    with pytest.raises(BookingNotFoundError):
        svc.earn_for_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            customer_id=CUSTOMER_ID,
        )

    repo.get_customer_for_update.assert_not_called()


def test_earn_uses_booking_price_from_db_not_caller() -> None:
    booking = _booking(price_cents=20_000)
    svc, session, _bookings, repo = _ledger_svc(booking=booking)
    customer = _customer()
    repo.get_customer_for_update.return_value = customer
    repo.get_transaction_by_idempotency_key.return_value = None

    @contextmanager
    def _nested():
        yield

    session.begin_nested = MagicMock(side_effect=lambda: _nested())

    result = svc.earn_for_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
    )

    assert result is not None
    assert result.amount_cents == 2_000
    assert customer.bonus_balance_cents == 2_000


def test_earn_idempotent_early_hit_reconciles_balance() -> None:
    booking = _booking()
    svc, session, _bookings, repo = _ledger_svc(booking=booking)
    customer = _customer(bonus_balance_cents=0)
    repo.get_customer_for_update.return_value = customer

    existing = BonusTransaction(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        booking_id=BOOKING_ID,
        transaction_type="earn",
        amount_cents=1_000,
        balance_after_cents=1_000,
        idempotency_key=f"earn:booking:{BOOKING_ID}",
    )
    existing.id = uuid.uuid4()
    existing.created_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    repo.get_transaction_by_idempotency_key.return_value = existing

    result = svc.earn_for_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
    )

    assert result is not None
    assert result.idempotent_replay is True
    assert customer.bonus_balance_cents == 1_000
    repo.flush.assert_called()
    session.begin_nested.assert_not_called()


def test_earn_integrity_error_replay_reconciles_balance() -> None:
    booking = _booking()
    svc, session, _bookings, repo = _ledger_svc(booking=booking)
    customer = _customer(bonus_balance_cents=0)
    repo.get_customer_for_update.return_value = customer

    existing = BonusTransaction(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        booking_id=BOOKING_ID,
        transaction_type="earn",
        amount_cents=1_000,
        balance_after_cents=1_000,
        idempotency_key=f"earn:booking:{BOOKING_ID}",
    )
    existing.id = uuid.uuid4()
    existing.created_at = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

    repo.get_transaction_by_idempotency_key.side_effect = [None, existing]

    @contextmanager
    def _nested_raises():
        yield
        raise IntegrityError("insert", {}, Exception())

    session.begin_nested = MagicMock(side_effect=lambda: _nested_raises())

    result = svc.earn_for_booking(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        customer_id=CUSTOMER_ID,
    )

    assert result is not None
    assert result.idempotent_replay is True
    assert result.transaction_id == existing.id
    assert customer.bonus_balance_cents == 1_000
    session.begin_nested.assert_called_once()


def test_post_ledger_entry_updates_balance_after_insert() -> None:
    session = MagicMock()
    svc = BonusLedgerService(session)
    repo = MagicMock()
    svc._repo = repo
    customer = _customer()
    repo.get_customer_for_update.return_value = customer
    repo.get_transaction_by_idempotency_key.return_value = None

    flush_calls: list[str] = []

    def _track_flush() -> None:
        flush_calls.append("flush")

    repo.flush.side_effect = _track_flush

    @contextmanager
    def _nested():
        yield

    session.begin_nested = MagicMock(side_effect=lambda: _nested())

    result = svc._post_ledger_entry(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        amount_cents=500,
        transaction_type="earn",
        booking_id=BOOKING_ID,
        description=None,
        idempotency_key=f"earn:booking:{BOOKING_ID}",
        created_by_user_id=None,
    )

    assert result.idempotent_replay is False
    assert customer.bonus_balance_cents == 500
    repo.add_transaction.assert_called_once()
    session.begin_nested.assert_called_once()
    assert flush_calls == ["flush", "flush"]


def test_earn_rejects_customer_mismatch() -> None:
    booking = _booking()
    svc, _session, _bookings, repo = _ledger_svc(booking=booking)

    with pytest.raises(BonusLedgerValidationError, match="customer_id"):
        svc.earn_for_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            customer_id=uuid.uuid4(),
        )

    repo.get_customer_for_update.assert_not_called()
