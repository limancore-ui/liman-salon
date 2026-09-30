from __future__ import annotations

import uuid
from datetime import datetime, time, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.booking import Booking
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import engine
from app.services.booking.manage_token import hash_manage_token, verify_manage_token
from app.services.customer.service import CustomerService
from app.services.public_booking.orchestrator import PublicBookingOrchestrator
from app.services.public_booking.service import PublicBookingService
from app.services.salon_public.service import SalonPublicService

UTC = timezone.utc
TEST_PEPPER = "integration-test-manage-token-pepper"


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


def _seed_bookable_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Token Test {suffix}",
        slug=f"token-test-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
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
        display_name="Bookable",
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
    session.add_all([staff, service])
    session.flush()
    session.add(
        StaffService(
            salon_id=salon.id,
            staff_id=staff.id,
            service_id=service.id,
        )
    )
    session.flush()
    return salon, staff, service


def test_public_create_persists_manage_token_hash_not_raw(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOOKING_MANAGE_TOKEN_PEPPER", TEST_PEPPER)
    get_settings.cache_clear()
    try:
        salon, staff, service = _seed_bookable_salon(db_session)
        as_of = datetime(2026, 6, 10, 8, 0, tzinfo=UTC)
        service_start = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)
        phone = f"+7702{uuid.uuid4().int % 10_000_000:07d}"

        orch = PublicBookingOrchestrator(
            SalonPublicService(db_session),
            CustomerService(db_session),
            PublicBookingService(
                db_session,
                public_booking_hold_seconds=900,
                booking_manage_token_pepper=TEST_PEPPER,
            ),
        )
        result = orch.create_public_booking_by_slug(
            slug=salon.slug,
            full_name="Token Guest",
            phone=phone,
            email=None,
            service_id=service.id,
            staff_id=staff.id,
            service_start=service_start,
            as_of=as_of,
        )

        assert result.manage_token
        assert result.manage_token != result.booking_id

        booking = db_session.scalar(
            select(Booking).where(
                Booking.salon_id == salon.id,
                Booking.id == result.booking_id,
            )
        )
        assert booking is not None
        assert booking.manage_token_hash is not None
        assert booking.manage_token_hash != result.manage_token
        assert len(booking.manage_token_hash) == 64
        assert verify_manage_token(
            result.manage_token,
            booking.manage_token_hash,
            pepper=TEST_PEPPER,
        )
        expected = hash_manage_token(result.manage_token, pepper=TEST_PEPPER)
        assert booking.manage_token_hash == expected
    finally:
        get_settings.cache_clear()
