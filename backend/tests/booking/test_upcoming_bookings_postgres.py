"""PostgreSQL-backed tests for upcoming booking list query (dashboard C7.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import insert, text
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


def _seed_upcoming_fixture(
    session: Session,
) -> tuple[Salon, Staff, Service, Customer, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Upcoming Test {suffix}",
        slug=f"upcoming-test-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()

    staff = Staff(
        salon_id=salon.id,
        display_name="Stylist One",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    service = Service(
        salon_id=salon.id,
        name="Haircut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=4500,
        is_active=True,
        sort_order=1,
    )
    customer = Customer(
        salon_id=salon.id,
        full_name="Jordan Lee",
        phone=f"+7720{uuid.uuid4().int % 10_000_000:07d}",
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
            starts_at=datetime(2026, 8, 10, 14, 0, tzinfo=UTC),
            ends_at=datetime(2026, 8, 10, 15, 0, tzinfo=UTC),
            status="confirmed",
            source="admin",
            price_cents=4500,
            currency_code="KZT",
            duration_minutes=60,
        )
    )
    session.flush()
    return salon, staff, service, customer, booking_id


def test_list_upcoming_bookings_starts_in_range_maps_all_row_fields(
    db_session: Session,
) -> None:
    salon, staff, service, customer, booking_id = _seed_upcoming_fixture(db_session)
    as_of = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    range_start = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 8, 11, 0, 0, tzinfo=UTC)
    starts_at = datetime(2026, 8, 10, 14, 0, tzinfo=UTC)

    rows = BookingRepository(db_session).list_upcoming_bookings_starts_in_range(
        salon_id=salon.id,
        range_start=range_start,
        range_end=range_end,
        as_of=as_of,
        limit=10,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.id == booking_id
    assert row.status == "confirmed"
    assert row.starts_at == starts_at
    assert row.ends_at == datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    assert row.price_cents == 4500
    assert row.customer_name == customer.full_name
    assert row.customer_phone == customer.phone
    assert row.staff_name == staff.display_name
    assert row.service_name == service.name


def test_list_upcoming_bookings_excludes_before_as_of(db_session: Session) -> None:
    salon, staff, service, _, _ = _seed_upcoming_fixture(db_session)
    as_of = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
    range_start = datetime(2026, 8, 12, 0, 0, tzinfo=UTC)
    range_end = datetime(2026, 8, 13, 0, 0, tzinfo=UTC)

    for full_name, start in (
        ("Early", datetime(2026, 8, 12, 10, 0, tzinfo=UTC)),
        ("Later", datetime(2026, 8, 12, 15, 0, tzinfo=UTC)),
    ):
        customer = Customer(
            salon_id=salon.id,
            full_name=full_name,
            phone=f"+7730{uuid.uuid4().int % 10_000_000:07d}",
        )
        db_session.add(customer)
        db_session.flush()
        db_session.execute(
            insert(Booking.__table__).values(
                id=uuid.uuid4(),
                salon_id=salon.id,
                customer_id=customer.id,
                staff_id=staff.id,
                service_id=service.id,
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                status="confirmed",
                source="admin",
                price_cents=4500,
                currency_code="KZT",
                duration_minutes=60,
            )
        )
    db_session.flush()

    rows = BookingRepository(db_session).list_upcoming_bookings_starts_in_range(
        salon_id=salon.id,
        range_start=range_start,
        range_end=range_end,
        as_of=as_of,
        limit=10,
    )

    assert len(rows) == 1
    assert rows[0].customer_name == "Later"
    assert rows[0].starts_at == datetime(2026, 8, 12, 15, 0, tzinfo=UTC)
