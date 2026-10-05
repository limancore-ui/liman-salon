"""PostgreSQL integration for BonusLedgerService (C20.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.bonus_transaction import BonusTransaction
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import engine
from app.services.bonus.errors import BonusLedgerNotFoundError, BonusLedgerValidationError
from app.services.bonus.service import BonusLedgerService

UTC = timezone.utc
STARTS = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
ENDS = datetime(2026, 9, 1, 11, 0, tzinfo=UTC)


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL test database not reachable",
)


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _seed_salon(
    session: Session,
    *,
    bonus_settings: dict | None = None,
) -> tuple[Salon, Customer, Booking]:
    suffix = uuid.uuid4().hex[:8]
    settings: dict = {"v": 1}
    if bonus_settings is not None:
        settings["bonuses"] = bonus_settings

    salon = Salon(
        name=f"Bonus E2E {suffix}",
        slug=f"bonus-e2e-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
        settings=settings,
    )
    session.add(salon)
    session.flush()

    for day in range(0, 7):
        session.add(
            WorkingHour(
                salon_id=salon.id,
                staff_id=None,
                day_of_week=day,
                start_time=time(0, 0),
                end_time=time(23, 59),
            )
        )

    staff = Staff(
        salon_id=salon.id,
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    service = Service(
        salon_id=salon.id,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=10_000,
        is_active=True,
        sort_order=1,
    )
    session.add_all([staff, service])
    session.flush()
    session.add(
        StaffService(
            salon_id=salon.id,
            staff_id=staff.id,
            service_id=service.id,
        )
    )

    customer = Customer(
        salon_id=salon.id,
        full_name="Guest",
        phone=f"+7700{suffix}",
        bonus_balance_cents=0,
    )
    session.add(customer)
    session.flush()

    booking = Booking(
        salon_id=salon.id,
        customer_id=customer.id,
        staff_id=staff.id,
        service_id=service.id,
        starts_at=STARTS,
        ends_at=ENDS,
        status="completed",
        price_cents=10_000,
        currency_code="KZT",
        duration_minutes=60,
    )
    session.add(booking)
    session.flush()
    return salon, customer, booking


def test_earn_disabled_is_no_op(db_session: Session) -> None:
    salon, customer, booking = _seed_salon(
        db_session,
        bonus_settings={"enabled": False, "earn_percentage": 10},
    )
    svc = BonusLedgerService(db_session)

    result = svc.earn_for_booking(
        salon_id=salon.id,
        booking_id=booking.id,
        customer_id=customer.id,
    )

    assert result is None
    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 0
    count = db_session.scalar(
        select(func.count())
        .select_from(BonusTransaction)
        .where(BonusTransaction.salon_id == salon.id)
    )
    assert count == 0


def test_earn_computes_from_settings(db_session: Session) -> None:
    salon, customer, booking = _seed_salon(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
    )
    svc = BonusLedgerService(db_session)

    result = svc.earn_for_booking(
        salon_id=salon.id,
        booking_id=booking.id,
        customer_id=customer.id,
    )

    assert result is not None
    assert result.idempotent_replay is False
    assert result.amount_cents == 1_000
    assert result.balance_after_cents == 1_000
    assert result.idempotency_key == f"earn:booking:{booking.id}"

    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 1_000


def test_earn_idempotent_retry(db_session: Session) -> None:
    salon, customer, booking = _seed_salon(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 5},
    )
    svc = BonusLedgerService(db_session)

    first = svc.earn_for_booking(
        salon_id=salon.id,
        booking_id=booking.id,
        customer_id=customer.id,
    )
    second = svc.earn_for_booking(
        salon_id=salon.id,
        booking_id=booking.id,
        customer_id=customer.id,
    )

    assert first is not None
    assert second is not None
    assert second.idempotent_replay is True
    assert second.transaction_id == first.transaction_id

    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 500
    count = db_session.scalar(
        select(func.count())
        .select_from(BonusTransaction)
        .where(BonusTransaction.salon_id == salon.id)
    )
    assert count == 1


def test_adjustment_updates_balance(db_session: Session) -> None:
    salon, customer, booking = _seed_salon(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
    )
    svc = BonusLedgerService(db_session)
    svc.earn_for_booking(
        salon_id=salon.id,
        booking_id=booking.id,
        customer_id=customer.id,
    )

    debit = svc.create_adjustment(
        salon_id=salon.id,
        customer_id=customer.id,
        amount_cents=-200,
        description="Manual correction",
    )

    assert debit.transaction_type == "adjustment"
    assert debit.amount_cents == -200
    assert debit.balance_after_cents == 800
    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 800


def test_adjustment_rejects_negative_balance(db_session: Session) -> None:
    salon, customer, _booking = _seed_salon(db_session, bonus_settings=None)
    svc = BonusLedgerService(db_session)

    with pytest.raises(BonusLedgerValidationError, match="negative"):
        svc.create_adjustment(
            salon_id=salon.id,
            customer_id=customer.id,
            amount_cents=-100,
            description="Too much",
        )


def test_adjustment_requires_description(db_session: Session) -> None:
    salon, customer, _booking = _seed_salon(db_session, bonus_settings=None)
    svc = BonusLedgerService(db_session)

    with pytest.raises(BonusLedgerValidationError, match="description"):
        svc.create_adjustment(
            salon_id=salon.id,
            customer_id=customer.id,
            amount_cents=50,
            description="   ",
        )


def test_tenant_isolation_wrong_salon(db_session: Session) -> None:
    salon, customer, _booking = _seed_salon(db_session, bonus_settings=None)
    other_salon_id = uuid.uuid4()
    svc = BonusLedgerService(db_session)

    with pytest.raises(BonusLedgerNotFoundError):
        svc.create_adjustment(
            salon_id=other_salon_id,
            customer_id=customer.id,
            amount_cents=10,
            description="Cross tenant",
        )
