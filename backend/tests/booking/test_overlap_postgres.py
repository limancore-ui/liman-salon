"""PostgreSQL-backed booking overlap / race tests (C4 audit)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, time, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import SessionLocal, engine
from app.services.booking.errors import BookingOverlapError, SlotNotAvailableError
from app.services.booking.service import BookingService
from app.services.customer.service import CustomerService, PublicCustomerResolveData

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


def _seed_bookable_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Overlap Test {suffix}",
        slug=f"overlap-test-{suffix}",
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


def _resolve_customer(
    session: Session,
    *,
    salon_id: uuid.UUID,
    full_name: str,
    phone: str,
) -> uuid.UUID:
    result = CustomerService(session).resolve_public_customer(
        salon_id=salon_id,
        data=PublicCustomerResolveData(full_name=full_name, phone=phone),
    )
    return result.customer_id


def _create_confirmed_booking(
    session: Session,
    *,
    salon_id: uuid.UUID,
    staff_id: uuid.UUID,
    service_id: uuid.UUID,
    customer_id: uuid.UUID,
    requested_start: datetime,
    as_of: datetime,
) -> None:
    BookingService(session).create_booking(
        salon_id=salon_id,
        customer_id=customer_id,
        staff_id=staff_id,
        service_id=service_id,
        requested_service_start=requested_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )


def test_same_staff_overlapping_interval_rejects_second_booking(
    db_session: Session,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    first_start = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)
    overlap_start = datetime(2026, 7, 2, 10, 30, tzinfo=UTC)

    customer_a = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="First",
        phone=f"+7710{uuid.uuid4().int % 10_000_000:07d}",
    )
    _create_confirmed_booking(
        db_session,
        salon_id=salon.id,
        staff_id=staff.id,
        service_id=service.id,
        customer_id=customer_a,
        requested_start=first_start,
        as_of=as_of,
    )

    customer_b = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Second",
        phone=f"+7711{uuid.uuid4().int % 10_000_000:07d}",
    )
    booking_svc = BookingService(db_session)
    with pytest.raises((SlotNotAvailableError, BookingOverlapError)):
        booking_svc.create_booking(
            salon_id=salon.id,
            customer_id=customer_b,
            staff_id=staff.id,
            service_id=service.id,
            requested_service_start=overlap_start,
            source="admin",
            status="confirmed",
            as_of=as_of,
        )


def test_adjacent_half_open_intervals_both_allowed(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
    first_start = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
    second_start = datetime(2026, 7, 4, 11, 0, tzinfo=UTC)

    customer_a = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Morning",
        phone=f"+7720{uuid.uuid4().int % 10_000_000:07d}",
    )
    first = BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_a,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=first_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )

    customer_b = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Noon",
        phone=f"+7721{uuid.uuid4().int % 10_000_000:07d}",
    )
    second = BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_b,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=second_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )

    assert first.starts_at == first_start
    assert first.ends_at == second_start
    assert second.starts_at == second_start
    assert second.booking_id != first.booking_id


def _cleanup_salon(salon_id: uuid.UUID) -> None:
    cleanup = SessionLocal()
    try:
        cleanup.execute(delete(Booking).where(Booking.salon_id == salon_id))
        cleanup.execute(delete(Customer).where(Customer.salon_id == salon_id))
        cleanup.execute(delete(StaffService).where(StaffService.salon_id == salon_id))
        cleanup.execute(delete(Service).where(Service.salon_id == salon_id))
        cleanup.execute(delete(Staff).where(Staff.salon_id == salon_id))
        cleanup.execute(delete(WorkingHour).where(WorkingHour.salon_id == salon_id))
        cleanup.execute(delete(Salon).where(Salon.id == salon_id))
        cleanup.commit()
    finally:
        cleanup.close()


def test_concurrent_transactions_one_success_one_overlap() -> None:
    seed = SessionLocal()
    salon_id: uuid.UUID
    staff_id: uuid.UUID
    service_id: uuid.UUID
    try:
        salon, staff, service = _seed_bookable_salon(seed)
        salon_id = salon.id
        staff_id = staff.id
        service_id = service.id
        seed.commit()
    finally:
        seed.close()

    as_of = datetime(2026, 7, 5, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 7, 6, 14, 0, tzinfo=UTC)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def _attempt(phone_suffix: int) -> None:
        barrier.wait()
        session = SessionLocal()
        try:
            customer = CustomerService(session).resolve_public_customer(
                salon_id=salon_id,
                data=PublicCustomerResolveData(
                    full_name=f"Race {phone_suffix}",
                    phone=f"+773{phone_suffix}{uuid.uuid4().int % 10_000_000:07d}",
                ),
            )
            BookingService(session).create_booking(
                salon_id=salon_id,
                customer_id=customer.customer_id,
                staff_id=staff_id,
                service_id=service_id,
                requested_service_start=service_start,
                source="admin",
                status="confirmed",
                as_of=as_of,
            )
            session.commit()
            label = "success"
        except (SlotNotAvailableError, BookingOverlapError):
            session.rollback()
            label = "overlap"
        finally:
            session.close()
        with lock:
            outcomes.append(label)

    threads = [
        threading.Thread(target=_attempt, args=(1,)),
        threading.Thread(target=_attempt, args=(2,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    try:
        assert sorted(outcomes) == ["overlap", "success"]
        verify = SessionLocal()
        try:
            rows = verify.scalars(
                select(Booking).where(
                    Booking.salon_id == salon_id,
                    Booking.staff_id == staff_id,
                    Booking.starts_at == service_start,
                )
            ).all()
            assert len(rows) == 1
        finally:
            verify.close()
    finally:
        _cleanup_salon(salon_id)


def test_public_booking_stale_precheck_returns_409_booking_overlap(
    db_session: Session,
) -> None:
    from fastapi.testclient import TestClient

    from app.api.deps import get_as_of, get_db
    from app.main import create_app
    from app.services.availability.service import AvailabilityService

    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 7, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 7, 8, 10, 0, tzinfo=UTC)

    holder = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Held",
        phone=f"+7740{uuid.uuid4().int % 10_000_000:07d}",
    )
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=holder,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=service_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_as_of] = lambda: as_of
    client = TestClient(app)
    payload = {
        "full_name": "Race Guest",
        "phone": f"+996{uuid.uuid4().int % 1_000_000_000:09d}",
        "service_id": str(service.id),
        "staff_id": str(staff.id),
        "service_start": service_start.isoformat(),
    }
    try:
        with patch.object(
            AvailabilityService,
            "is_service_slot_available",
            return_value=True,
        ):
            response = client.post(
                f"/api/v1/public/salons/{salon.slug}/bookings",
                json=payload,
            )
        assert response.status_code == 409
        assert response.json()["code"] == "slot_not_available"
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_write_path_expires_stale_pending_overlapping_slot(db_session: Session) -> None:
    from app.core.config import get_settings

    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    service_start = datetime(2026, 8, 2, 10, 0, tzinfo=UTC)
    service_end = service_start + timedelta(minutes=service.duration_minutes)

    holder_id = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Stale Hold",
        phone=f"+7750{uuid.uuid4().int % 10_000_000:07d}",
    )
    stale = Booking(
        salon_id=salon.id,
        customer_id=holder_id,
        staff_id=staff.id,
        service_id=service.id,
        starts_at=service_start,
        ends_at=service_end,
        status="pending",
        source="public",
        price_cents=service.price_cents,
        currency_code=salon.currency_code,
        duration_minutes=service.duration_minutes,
        expires_at=as_of - timedelta(seconds=get_settings().public_booking_hold_seconds),
    )
    db_session.add(stale)
    db_session.flush()
    stale_id = stale.id

    new_customer = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="New Booking",
        phone=f"+7751{uuid.uuid4().int % 10_000_000:07d}",
    )
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=new_customer,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=service_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )

    db_session.expire(stale)
    refreshed = db_session.get(Booking, stale_id)
    assert refreshed is not None
    assert refreshed.status == "expired"
