"""Tests for global pending-hold expiry sweeper (C8.8)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.session import engine
from app.services.booking.errors import BookingValidationError
from app.services.booking.repository import BookingRepository
from app.services.booking.service import BookingService

UTC = timezone.utc
AS_OF = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
SLOT_START = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
SLOT_END = datetime(2026, 3, 20, 11, 0, tzinfo=UTC)


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


def _seed_salon_with_booking_entities(session: Session) -> tuple[Salon, Staff, Service, Customer]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Expire Sweep {suffix}",
        slug=f"expire-sweep-{suffix}",
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
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )
    customer = Customer(
        salon_id=salon.id,
        full_name="Guest",
        phone=f"+7760{uuid.uuid4().int % 10_000_000:07d}",
    )
    session.add_all([staff, service, customer])
    session.flush()
    return salon, staff, service, customer


def _insert_booking(
    session: Session,
    *,
    salon: Salon,
    staff: Staff,
    service: Service,
    customer: Customer,
    status: str,
    expires_at: datetime | None,
    starts_at: datetime = SLOT_START,
    ends_at: datetime = SLOT_END,
) -> uuid.UUID:
    booking_id = uuid.uuid4()
    session.execute(
        insert(Booking.__table__).values(
            id=booking_id,
            salon_id=salon.id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
            source="public" if status == "pending" else "admin",
            price_cents=service.price_cents,
            currency_code=salon.currency_code,
            duration_minutes=service.duration_minutes,
            expires_at=expires_at,
        )
    )
    session.flush()
    return booking_id


def test_service_rejects_naive_as_of() -> None:
    session = MagicMock()
    svc = BookingService(session)
    with pytest.raises(BookingValidationError, match="as_of must be timezone-aware"):
        svc.expire_all_stale_pending_holds(
            as_of=datetime(2026, 1, 1, 12, 0),
        )


def test_a_stale_pending_hold_expires(db_session: Session) -> None:
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    booking_id = _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="pending",
        expires_at=AS_OF - timedelta(minutes=1),
    )

    count = BookingService(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 1
    row = db_session.get(Booking, booking_id)
    assert row is not None
    assert row.status == "expired"
    assert row.updated_at == AS_OF


def test_b_active_pending_hold_unchanged(db_session: Session) -> None:
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    booking_id = _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="pending",
        expires_at=AS_OF + timedelta(minutes=5),
    )

    count = BookingService(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 0
    row = db_session.get(Booking, booking_id)
    assert row is not None
    assert row.status == "pending"


def test_c_confirmed_booking_unchanged(db_session: Session) -> None:
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    booking_id = _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="confirmed",
        expires_at=None,
    )

    count = BookingService(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 0
    row = db_session.get(Booking, booking_id)
    assert row is not None
    assert row.status == "confirmed"


def test_d_already_expired_unchanged(db_session: Session) -> None:
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    booking_id = _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="expired",
        expires_at=AS_OF - timedelta(hours=1),
    )
    before = db_session.get(Booking, booking_id)
    assert before is not None
    updated_before = before.updated_at

    count = BookingService(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 0
    row = db_session.get(Booking, booking_id)
    assert row is not None
    assert row.status == "expired"
    assert row.updated_at == updated_before


def test_e_pending_null_expires_at_unchanged(db_session: Session) -> None:
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    booking_id = _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="pending",
        expires_at=None,
    )

    count = BookingService(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 0
    row = db_session.get(Booking, booking_id)
    assert row is not None
    assert row.status == "pending"
    assert row.expires_at is None


def test_f_tenant_isolation_expires_per_salon_stale_only(db_session: Session) -> None:
    salon_a, staff_a, service_a, customer_a = _seed_salon_with_booking_entities(db_session)
    salon_b, staff_b, service_b, customer_b = _seed_salon_with_booking_entities(db_session)

    stale_a = _insert_booking(
        db_session,
        salon=salon_a,
        staff=staff_a,
        service=service_a,
        customer=customer_a,
        status="pending",
        expires_at=AS_OF - timedelta(seconds=30),
    )
    active_b = _insert_booking(
        db_session,
        salon=salon_b,
        staff=staff_b,
        service=service_b,
        customer=customer_b,
        status="pending",
        expires_at=AS_OF + timedelta(hours=1),
    )
    stale_b = _insert_booking(
        db_session,
        salon=salon_b,
        staff=staff_b,
        service=service_b,
        customer=customer_b,
        status="pending",
        expires_at=AS_OF,
        starts_at=SLOT_START + timedelta(days=1),
        ends_at=SLOT_END + timedelta(days=1),
    )

    count = BookingService(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 2
    assert db_session.get(Booking, stale_a).status == "expired"
    assert db_session.get(Booking, stale_b).status == "expired"
    assert db_session.get(Booking, active_b).status == "pending"


def test_window_scoped_expire_unchanged_non_overlapping_stale(db_session: Session) -> None:
    """Global sweep expires stale holds that window-scoped expiry would skip."""
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    booking_id = _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="pending",
        expires_at=AS_OF - timedelta(minutes=1),
    )
    repo = BookingRepository(db_session)
    window_start = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    window_end = datetime(2026, 4, 1, 1, 0, tzinfo=UTC)

    window_count = repo.expire_stale_pending_holds(
        salon_id=salon.id,
        staff_id=staff.id,
        window_start=window_start,
        window_end=window_end,
        as_of=AS_OF,
    )
    assert window_count == 0
    assert db_session.get(Booking, booking_id).status == "pending"

    global_count = repo.expire_all_stale_pending_holds(as_of=AS_OF)
    assert global_count == 1
    assert db_session.get(Booking, booking_id).status == "expired"


def test_repository_expire_all_rowcount_matches_pending_stale(db_session: Session) -> None:
    salon, staff, service, customer = _seed_salon_with_booking_entities(db_session)
    for offset_minutes in (5, 10, 15):
        _insert_booking(
            db_session,
            salon=salon,
            staff=staff,
            service=service,
            customer=customer,
            status="pending",
            expires_at=AS_OF - timedelta(minutes=offset_minutes),
            starts_at=SLOT_START + timedelta(hours=offset_minutes),
            ends_at=SLOT_END + timedelta(hours=offset_minutes),
        )
    _insert_booking(
        db_session,
        salon=salon,
        staff=staff,
        service=service,
        customer=customer,
        status="pending",
        expires_at=AS_OF + timedelta(minutes=1),
        starts_at=SLOT_START + timedelta(days=2),
        ends_at=SLOT_END + timedelta(days=2),
    )

    count = BookingRepository(db_session).expire_all_stale_pending_holds(as_of=AS_OF)

    assert count == 3
    statuses = db_session.scalars(
        select(Booking.status).where(Booking.salon_id == salon.id)
    ).all()
    assert statuses.count("expired") == 3
    assert statuses.count("pending") == 1
