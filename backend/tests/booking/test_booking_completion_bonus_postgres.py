"""PostgreSQL: atomic booking completion + bonus earn (C20.2.2)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from unittest.mock import patch

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
from app.services.bonus.errors import BonusLedgerValidationError
from app.services.bonus.service import BonusLedgerService
from app.services.booking.errors import BookingNotFoundError
from app.services.booking.service import BookingService

UTC = timezone.utc
AS_OF = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
STARTS = datetime(2026, 9, 2, 10, 0, tzinfo=UTC)
ENDS = datetime(2026, 9, 2, 11, 0, tzinfo=UTC)


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


def _seed_confirmed_booking(
    session: Session,
    *,
    bonus_settings: dict | None,
    price_cents: int = 10_000,
) -> tuple[Salon, Customer, Booking]:
    suffix = uuid.uuid4().hex[:8]
    settings: dict = {"v": 1}
    if bonus_settings is not None:
        settings["bonuses"] = bonus_settings

    salon = Salon(
        name=f"Complete Bonus {suffix}",
        slug=f"complete-bonus-{suffix}",
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
        price_cents=50_000,
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
        phone=f"+7701{suffix}",
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
        status="confirmed",
        source="admin",
        price_cents=price_cents,
        currency_code="KZT",
        duration_minutes=60,
        confirmed_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )
    session.add(booking)
    session.flush()
    return salon, customer, booking


def _booking_service(session: Session) -> BookingService:
    bonus = BonusLedgerService(session)
    return BookingService(session, bonus_ledger=bonus)


def _count_earn_rows(session: Session, *, salon_id: uuid.UUID) -> int:
    return session.scalar(
        select(func.count())
        .select_from(BonusTransaction)
        .where(
            BonusTransaction.salon_id == salon_id,
            BonusTransaction.transaction_type == "earn",
        )
    ) or 0


def test_confirmed_to_completed_one_earn_and_balance(db_session: Session) -> None:
    salon, customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
        price_cents=10_000,
    )
    svc = _booking_service(db_session)

    result = svc.admin_complete_visit(
        salon_id=salon.id,
        booking_id=booking.id,
        as_of=AS_OF,
    )

    assert result.status == "completed"
    assert _count_earn_rows(db_session, salon_id=salon.id) == 1
    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 1_000

    row = db_session.scalar(
        select(BonusTransaction).where(
            BonusTransaction.salon_id == salon.id,
            BonusTransaction.idempotency_key == f"earn:booking:{booking.id}",
        )
    )
    assert row is not None
    assert row.amount_cents == 1_000


def test_repeat_earn_idempotent_no_duplicate(db_session: Session) -> None:
    salon, customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
    )
    svc = _booking_service(db_session)
    bonus = BonusLedgerService(db_session)

    svc.admin_complete_visit(
        salon_id=salon.id,
        booking_id=booking.id,
        as_of=AS_OF,
    )

    bonus.earn_for_booking(
        salon_id=salon.id,
        booking_id=booking.id,
        customer_id=customer.id,
    )

    assert _count_earn_rows(db_session, salon_id=salon.id) == 1
    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 1_000


def test_disabled_bonuses_no_ledger_row(db_session: Session) -> None:
    salon, customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": False, "earn_percentage": 10},
    )
    svc = _booking_service(db_session)

    svc.admin_complete_visit(
        salon_id=salon.id,
        booking_id=booking.id,
        as_of=AS_OF,
    )

    assert _count_earn_rows(db_session, salon_id=salon.id) == 0
    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 0


def test_zero_percent_earn_is_no_op(db_session: Session) -> None:
    salon, customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 0},
    )
    svc = _booking_service(db_session)

    svc.admin_complete_visit(
        salon_id=salon.id,
        booking_id=booking.id,
        as_of=AS_OF,
    )

    assert _count_earn_rows(db_session, salon_id=salon.id) == 0
    db_session.refresh(customer)
    assert customer.bonus_balance_cents == 0


def test_earn_amount_from_booking_price_not_catalog(db_session: Session) -> None:
    salon, customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
        price_cents=7_500,
    )
    svc = _booking_service(db_session)

    svc.admin_complete_visit(
        salon_id=salon.id,
        booking_id=booking.id,
        as_of=AS_OF,
    )

    row = db_session.scalar(
        select(BonusTransaction).where(
            BonusTransaction.salon_id == salon.id,
            BonusTransaction.booking_id == booking.id,
        )
    )
    assert row is not None
    assert row.amount_cents == 750


def test_ledger_failure_rolls_back_completion(db_session: Session) -> None:
    salon, _customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
    )
    svc = _booking_service(db_session)
    booking_id = booking.id

    savepoint = db_session.begin_nested()
    with patch.object(
        BonusLedgerService,
        "earn_for_booking",
        side_effect=BonusLedgerValidationError("forced failure"),
    ):
        with pytest.raises(BonusLedgerValidationError, match="forced failure"):
            svc.admin_complete_visit(
                salon_id=salon.id,
                booking_id=booking_id,
                as_of=AS_OF,
            )

    savepoint.rollback()
    db_session.expire_all()
    persisted = db_session.get(Booking, booking_id)
    assert persisted is not None
    assert persisted.status == "confirmed"
    assert persisted.completed_at is None
    assert _count_earn_rows(db_session, salon_id=salon.id) == 0


def test_tenant_isolation_earn_scoped_to_salon(db_session: Session) -> None:
    salon_a, customer_a, booking_a = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
        price_cents=10_000,
    )
    salon_b, customer_b, booking_b = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
        price_cents=10_000,
    )
    svc = _booking_service(db_session)

    svc.admin_complete_visit(
        salon_id=salon_a.id,
        booking_id=booking_a.id,
        as_of=AS_OF,
    )

    assert _count_earn_rows(db_session, salon_id=salon_a.id) == 1
    assert _count_earn_rows(db_session, salon_id=salon_b.id) == 0

    db_session.refresh(customer_a)
    db_session.refresh(customer_b)
    assert customer_a.bonus_balance_cents == 1_000
    assert customer_b.bonus_balance_cents == 0

    with pytest.raises(BookingNotFoundError):
        svc.admin_complete_visit(
            salon_id=salon_a.id,
            booking_id=booking_b.id,
            as_of=AS_OF,
        )


def test_atomic_completion_and_bonus_commits_together(db_session: Session) -> None:
    salon, customer, booking = _seed_confirmed_booking(
        db_session,
        bonus_settings={"enabled": True, "earn_percentage": 10},
    )
    svc = _booking_service(db_session)

    svc.admin_complete_visit(
        salon_id=salon.id,
        booking_id=booking.id,
        as_of=AS_OF,
    )
    db_session.flush()

    db_session.refresh(booking)
    db_session.refresh(customer)
    assert booking.status == "completed"
    assert booking.completed_at == AS_OF
    assert customer.bonus_balance_cents == 1_000
    assert _count_earn_rows(db_session, salon_id=salon.id) == 1
