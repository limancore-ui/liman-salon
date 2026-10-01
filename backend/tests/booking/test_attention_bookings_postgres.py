"""PostgreSQL-backed tests for operational attention booking list (dashboard C11.z)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.session import engine
from app.services.booking.repository import BookingRepository

UTC = timezone.utc


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


def _seed_salon_booking(
    session: Session,
    *,
    full_name: str,
    starts_at: datetime,
    status: str,
) -> tuple[Salon, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Attention Test {suffix}",
        slug=f"attention-test-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()

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
        price_cents=4500,
        is_active=True,
        sort_order=1,
    )
    customer = Customer(
        salon_id=salon.id,
        full_name=full_name,
        phone=f"+7740{uuid.uuid4().int % 10_000_000:07d}",
    )
    session.add_all([staff, service, customer])
    session.flush()

    booking_id = uuid.uuid4()
    session.execute(
        insert(Booking.__table__).values(
            id=booking_id,
            salon_id=salon.id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            status=status,
            source="admin",
            price_cents=4500,
            currency_code="KZT",
            duration_minutes=60,
        )
    )
    session.flush()
    return salon, booking_id


def test_list_attention_includes_overdue_pending_before_as_of(
    db_session: Session,
) -> None:
    salon, booking_id = _seed_salon_booking(
        db_session,
        full_name="Overdue Pending",
        starts_at=datetime(2026, 8, 10, 9, 0, tzinfo=UTC),
        status="pending",
    )
    range_start = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)

    rows = BookingRepository(db_session).list_attention_bookings_starts_in_range(
        salon_id=salon.id,
        range_start=range_start,
        range_end=range_end,
        limit=25,
    )

    assert len(rows) == 1
    assert rows[0].id == booking_id
    assert rows[0].status == "pending"


def _add_booking_to_salon(
    session: Session,
    salon: Salon,
    *,
    full_name: str,
    starts_at: datetime,
    status: str,
) -> None:
    staff_id = session.scalar(
        select(Staff.id).where(Staff.salon_id == salon.id).limit(1)
    )
    service_id = session.scalar(
        select(Service.id).where(Service.salon_id == salon.id).limit(1)
    )
    customer = Customer(
        salon_id=salon.id,
        full_name=full_name,
        phone=f"+7750{uuid.uuid4().int % 10_000_000:07d}",
    )
    session.add(customer)
    session.flush()
    session.execute(
        insert(Booking.__table__).values(
            id=uuid.uuid4(),
            salon_id=salon.id,
            customer_id=customer.id,
            staff_id=staff_id,
            service_id=service_id,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            status=status,
            source="admin",
            price_cents=4500,
            currency_code="KZT",
            duration_minutes=60,
        )
    )
    session.flush()


def test_list_attention_excludes_completed_and_orders_by_starts_at(
    db_session: Session,
) -> None:
    salon, _ = _seed_salon_booking(
        db_session,
        full_name="Later",
        starts_at=datetime(2026, 8, 11, 15, 0, tzinfo=UTC),
        status="confirmed",
    )
    _add_booking_to_salon(
        db_session,
        salon,
        full_name="Completed",
        starts_at=datetime(2026, 8, 11, 11, 0, tzinfo=UTC),
        status="completed",
    )
    _add_booking_to_salon(
        db_session,
        salon,
        full_name="Early",
        starts_at=datetime(2026, 8, 11, 10, 0, tzinfo=UTC),
        status="pending",
    )
    range_start = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 8, 12, 0, 0, tzinfo=UTC)

    rows = BookingRepository(db_session).list_attention_bookings_starts_in_range(
        salon_id=salon.id,
        range_start=range_start,
        range_end=range_end,
        limit=25,
    )

    assert len(rows) == 2
    assert rows[0].customer_name == "Early"
    assert rows[1].customer_name == "Later"
    assert all(r.status in ("pending", "confirmed", "in_progress") for r in rows)


def test_list_attention_scoped_by_salon_id(db_session: Session) -> None:
    salon_a, _ = _seed_salon_booking(
        db_session,
        full_name="Salon A",
        starts_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
        status="confirmed",
    )
    salon_b, _ = _seed_salon_booking(
        db_session,
        full_name="Salon B",
        starts_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC),
        status="confirmed",
    )
    range_start = datetime(2026, 8, 12, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)

    rows = BookingRepository(db_session).list_attention_bookings_starts_in_range(
        salon_id=salon_a.id,
        range_start=range_start,
        range_end=range_end,
        limit=25,
    )

    assert len(rows) == 1
    assert rows[0].customer_name == "Salon A"
    assert salon_a.id != salon_b.id
