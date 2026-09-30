"""PostgreSQL-backed booking reschedule overlap / race tests (C6.2.3)."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import SessionLocal, engine
from app.services.booking.errors import BookingOverlapError, SlotNotAvailableError
from app.services.booking.manage_token import hash_manage_token
from app.services.booking.service import BookingService
from app.services.customer.service import CustomerService, PublicCustomerResolveData

UTC = timezone.utc
RAW_TOKEN = "postgres-reschedule-manage-token"
PEPPER = get_settings().booking_manage_token_pepper


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
        name=f"Reschedule Overlap {suffix}",
        slug=f"reschedule-overlap-{suffix}",
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


def _create_confirmed_with_token(
    session: Session,
    *,
    salon_id: uuid.UUID,
    staff_id: uuid.UUID,
    service_id: uuid.UUID,
    customer_id: uuid.UUID,
    requested_start: datetime,
    as_of: datetime,
    token_hash: str,
) -> uuid.UUID:
    svc = BookingService(session)
    result = svc.create_booking(
        salon_id=salon_id,
        customer_id=customer_id,
        staff_id=staff_id,
        service_id=service_id,
        requested_service_start=requested_start,
        source="public",
        status="confirmed",
        as_of=as_of,
        manage_token_hash=token_hash,
    )
    return result.booking_id


def test_reschedule_same_slot_succeeds_excluding_self(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    start = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)
    token_hash = hash_manage_token(RAW_TOKEN, pepper=PEPPER)

    customer = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Self",
        phone=f"+7750{uuid.uuid4().int % 10_000_000:07d}",
    )
    booking_id = _create_confirmed_with_token(
        db_session,
        salon_id=salon.id,
        staff_id=staff.id,
        service_id=service.id,
        customer_id=customer,
        requested_start=start,
        as_of=as_of,
        token_hash=token_hash,
    )

    result = BookingService(db_session).reschedule_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        token=RAW_TOKEN,
        new_staff_id=staff.id,
        new_service_start=start,
        as_of=as_of,
    )
    assert result.booking_id == booking_id
    assert result.service_start == start


def test_reschedule_into_occupied_slot_rejected(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 3, 8, 0, tzinfo=UTC)
    first_start = datetime(2026, 7, 4, 10, 0, tzinfo=UTC)
    target_start = datetime(2026, 7, 4, 10, 30, tzinfo=UTC)
    token_hash = hash_manage_token(RAW_TOKEN, pepper=PEPPER)

    blocker = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Blocker",
        phone=f"+7751{uuid.uuid4().int % 10_000_000:07d}",
    )
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=blocker,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=first_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )

    mover = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Mover",
        phone=f"+7752{uuid.uuid4().int % 10_000_000:07d}",
    )
    booking_id = _create_confirmed_with_token(
        db_session,
        salon_id=salon.id,
        staff_id=staff.id,
        service_id=service.id,
        customer_id=mover,
        requested_start=datetime(2026, 7, 4, 14, 0, tzinfo=UTC),
        as_of=as_of,
        token_hash=token_hash,
    )

    with pytest.raises((SlotNotAvailableError, BookingOverlapError)):
        BookingService(db_session).reschedule_booking(
            salon_id=salon.id,
            booking_id=booking_id,
            token=RAW_TOKEN,
            new_staff_id=staff.id,
            new_service_start=target_start,
            as_of=as_of,
        )


def test_reschedule_updates_row_not_insert(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 5, 8, 0, tzinfo=UTC)
    old_start = datetime(2026, 7, 6, 9, 0, tzinfo=UTC)
    new_start = datetime(2026, 7, 6, 15, 0, tzinfo=UTC)
    token_hash = hash_manage_token(RAW_TOKEN, pepper=PEPPER)

    customer = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Update",
        phone=f"+7753{uuid.uuid4().int % 10_000_000:07d}",
    )
    booking_id = _create_confirmed_with_token(
        db_session,
        salon_id=salon.id,
        staff_id=staff.id,
        service_id=service.id,
        customer_id=customer,
        requested_start=old_start,
        as_of=as_of,
        token_hash=token_hash,
    )

    BookingService(db_session).reschedule_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        token=RAW_TOKEN,
        new_staff_id=staff.id,
        new_service_start=new_start,
        as_of=as_of,
    )

    rows = db_session.scalars(
        select(Booking).where(Booking.salon_id == salon.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].id == booking_id
    assert rows[0].starts_at == new_start


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


def test_concurrent_reschedule_to_same_slot_one_overlap() -> None:
    seed = SessionLocal()
    salon_id: uuid.UUID
    staff_id: uuid.UUID
    service_id: uuid.UUID
    booking_a: uuid.UUID
    booking_b: uuid.UUID
    token_a = "concurrent-reschedule-token-a"
    token_b = "concurrent-reschedule-token-b"
    try:
        salon, staff, service = _seed_bookable_salon(seed)
        salon_id = salon.id
        staff_id = staff.id
        service_id = service.id
        as_of = datetime(2026, 7, 7, 8, 0, tzinfo=UTC)
        start_a = datetime(2026, 7, 8, 9, 0, tzinfo=UTC)
        start_b = datetime(2026, 7, 8, 11, 0, tzinfo=UTC)
        target = datetime(2026, 7, 8, 14, 0, tzinfo=UTC)

        cust_a = CustomerService(seed).resolve_public_customer(
            salon_id=salon_id,
            data=PublicCustomerResolveData(
                full_name="Race A",
                phone=f"+7760{uuid.uuid4().int % 10_000_000:07d}",
            ),
        )
        cust_b = CustomerService(seed).resolve_public_customer(
            salon_id=salon_id,
            data=PublicCustomerResolveData(
                full_name="Race B",
                phone=f"+7761{uuid.uuid4().int % 10_000_000:07d}",
            ),
        )
        svc = BookingService(seed)
        booking_a = svc.create_booking(
            salon_id=salon_id,
            customer_id=cust_a.customer_id,
            staff_id=staff_id,
            service_id=service_id,
            requested_service_start=start_a,
            source="public",
            status="confirmed",
            as_of=as_of,
            manage_token_hash=hash_manage_token(token_a, pepper=PEPPER),
        ).booking_id
        booking_b = svc.create_booking(
            salon_id=salon_id,
            customer_id=cust_b.customer_id,
            staff_id=staff_id,
            service_id=service_id,
            requested_service_start=start_b,
            source="public",
            status="confirmed",
            as_of=as_of,
            manage_token_hash=hash_manage_token(token_b, pepper=PEPPER),
        ).booking_id
        seed.commit()
    finally:
        seed.close()

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    lock = threading.Lock()

    def _attempt(booking_id: uuid.UUID, token: str) -> None:
        barrier.wait()
        session = SessionLocal()
        try:
            BookingService(session).reschedule_booking(
                salon_id=salon_id,
                booking_id=booking_id,
                token=token,
                new_staff_id=staff_id,
                new_service_start=target,
                as_of=as_of,
            )
            session.commit()
            label = "success"
        except BookingOverlapError:
            session.rollback()
            label = "overlap"
        finally:
            session.close()
        with lock:
            outcomes.append(label)

    threads = [
        threading.Thread(target=_attempt, args=(booking_a, token_a)),
        threading.Thread(target=_attempt, args=(booking_b, token_b)),
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
                    Booking.starts_at == target,
                    Booking.status == "confirmed",
                )
            ).all()
            assert len(rows) == 1
        finally:
            verify.close()
    finally:
        _cleanup_salon(salon_id)


def test_public_reschedule_stale_precheck_returns_409_booking_overlap(
    db_session: Session,
) -> None:
    from fastapi.testclient import TestClient

    from app.api.deps import get_as_of, get_db
    from app.main import create_app
    from app.services.availability.service import AvailabilityService

    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 7, 9, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)
    token_hash = hash_manage_token(RAW_TOKEN, pepper=PEPPER)

    holder = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Held",
        phone=f"+7770{uuid.uuid4().int % 10_000_000:07d}",
    )
    booking_id = _create_confirmed_with_token(
        db_session,
        salon_id=salon.id,
        staff_id=staff.id,
        service_id=service.id,
        customer_id=holder,
        requested_start=datetime(2026, 7, 10, 8, 0, tzinfo=UTC),
        as_of=as_of,
        token_hash=token_hash,
    )

    blocker = _resolve_customer(
        db_session,
        salon_id=salon.id,
        full_name="Block",
        phone=f"+7771{uuid.uuid4().int % 10_000_000:07d}",
    )
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=blocker,
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
        "token": RAW_TOKEN,
        "staff_id": str(staff.id),
        "service_start": service_start.isoformat(),
    }
    try:
        with patch.object(
            AvailabilityService,
            "is_occupied_interval_available",
            return_value=True,
        ):
            response = client.post(
                f"/api/v1/public/salons/{salon.slug}/bookings/{booking_id}/reschedule",
                json=payload,
            )
        assert response.status_code == 409
        assert response.json()["code"] == "booking_overlap"
    finally:
        client.close()
        app.dependency_overrides.clear()
