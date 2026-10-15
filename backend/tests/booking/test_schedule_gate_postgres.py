"""PostgreSQL: booking create/reschedule under shared schedule gate locks."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, time, timezone

import pytest
from sqlalchemy import delete, text
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
from app.core.config import get_settings
from app.services.booking.manage_token import generate_manage_token, hash_manage_token
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


def _seed_bookable_salon(session: Session) -> tuple[Salon, Staff, Service]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Gate Test {suffix}",
        slug=f"gate-test-{suffix}",
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
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    session.add(staff)
    session.flush()

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
    session.add(service)
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


def _cleanup_salon(salon_id: uuid.UUID) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(Booking).where(Booking.salon_id == salon_id))
        session.execute(delete(Customer).where(Customer.salon_id == salon_id))
        session.execute(delete(StaffService).where(StaffService.salon_id == salon_id))
        session.execute(delete(Service).where(Service.salon_id == salon_id))
        session.execute(delete(Staff).where(Staff.salon_id == salon_id))
        session.execute(delete(WorkingHour).where(WorkingHour.salon_id == salon_id))
        session.execute(delete(Salon).where(Salon.id == salon_id))
        session.commit()
    finally:
        session.close()


def test_concurrent_create_booking_one_success_one_conflict() -> None:
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

    as_of = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 8, 6, 14, 0, tzinfo=UTC)
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
                    full_name=f"Gate Race {phone_suffix}",
                    phone=f"+775{phone_suffix}{uuid.uuid4().int % 10_000_000:07d}",
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
            label = "conflict"
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
        assert sorted(outcomes) == ["conflict", "success"]
    finally:
        _cleanup_salon(salon_id)


def test_reschedule_under_shared_gate_commits() -> None:
    session = SessionLocal()
    salon_id: uuid.UUID
    staff_id: uuid.UUID
    booking_id: uuid.UUID
    token: str
    as_of = datetime(2026, 8, 10, 8, 0, tzinfo=UTC)
    try:
        salon, staff, service = _seed_bookable_salon(session)
        start = datetime(2026, 8, 11, 10, 0, tzinfo=UTC)
        customer = CustomerService(session).resolve_public_customer(
            salon_id=salon.id,
            data=PublicCustomerResolveData(
                full_name="Reschedule Guest",
                phone=f"+776{uuid.uuid4().int % 10_000_000:07d}",
            ),
        )
        token = generate_manage_token()
        created = BookingService(session).create_booking(
            salon_id=salon.id,
            customer_id=customer.customer_id,
            staff_id=staff.id,
            service_id=service.id,
            requested_service_start=start,
            source="public",
            status="pending",
            as_of=as_of,
            manage_token_hash=hash_manage_token(
                token,
                pepper=get_settings().booking_manage_token_pepper,
            ),
        )
        session.commit()
        salon_id = salon.id
        staff_id = staff.id
        booking_id = created.booking_id
    finally:
        session.close()

    new_start = datetime(2026, 8, 12, 15, 0, tzinfo=UTC)
    reschedule_session = SessionLocal()
    try:
        BookingService(reschedule_session).reschedule_booking(
            salon_id=salon_id,
            booking_id=booking_id,
            token=token,
            new_staff_id=staff_id,
            new_service_start=new_start,
            as_of=as_of,
        )
        reschedule_session.commit()
    finally:
        reschedule_session.close()

    verify = SessionLocal()
    try:
        row = verify.get(Booking, booking_id)
        assert row is not None
        assert row.starts_at == new_start
    finally:
        verify.close()
        _cleanup_salon(salon_id)
