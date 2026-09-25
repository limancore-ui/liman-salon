"""Regression: one request-scoped session owns commit; booking must not nest begin()."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
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
from app.db.session import SessionLocal, engine, get_db
from app.services.booking.errors import BookingNotFoundError, BookingOverlapError
from app.services.booking.service import BookingService
from app.services.customer.service import CustomerService, PublicCustomerResolveData
from app.services.public_booking.orchestrator import PublicBookingOrchestrator
from app.services.public_booking.service import PublicBookingService
from app.services.salon_public.service import SalonPublicService

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
        name=f"Txn Test {suffix}",
        slug=f"txn-test-{suffix}",
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


def _orchestrator_for(session: Session) -> PublicBookingOrchestrator:
    return PublicBookingOrchestrator(
        SalonPublicService(session),
        CustomerService(session),
        PublicBookingService(session, public_booking_hold_seconds=900),
    )


def test_orchestrated_flow_after_customer_flush(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 6, 2, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
    phone = f"+7700{uuid.uuid4().int % 10_000_000:07d}"

    orch = _orchestrator_for(db_session)
    result = orch.create_public_booking_by_slug(
        slug=salon.slug,
        full_name="New Guest",
        phone=phone,
        email=None,
        service_id=service.id,
        staff_id=staff.id,
        service_start=service_start,
        as_of=as_of,
    )

    assert result.customer_id is not None
    assert result.booking_id is not None
    customer = db_session.scalar(
        select(Customer).where(
            Customer.salon_id == salon.id,
            Customer.id == result.customer_id,
        )
    )
    booking = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == result.booking_id,
        )
    )
    assert customer is not None
    assert booking is not None


def test_get_db_success_commits_customer_and_booking() -> None:
    salon_id: uuid.UUID
    customer_id: uuid.UUID
    booking_id: uuid.UUID
    phone = f"+7701{uuid.uuid4().int % 10_000_000:07d}"
    slug: str
    staff_id: uuid.UUID
    service_id: uuid.UUID
    as_of = datetime(2026, 6, 3, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 6, 3, 11, 0, tzinfo=UTC)

    gen = get_db()
    session = next(gen)
    salon, staff, service = _seed_bookable_salon(session)
    slug = salon.slug
    salon_id = salon.id
    staff_id = staff.id
    service_id = service.id
    orch = _orchestrator_for(session)
    result = orch.create_public_booking_by_slug(
        slug=slug,
        full_name="Committed Guest",
        phone=phone,
        email=None,
        service_id=service_id,
        staff_id=staff_id,
        service_start=service_start,
        as_of=as_of,
    )
    customer_id = result.customer_id
    booking_id = result.booking_id
    try:
        next(gen)
    except StopIteration:
        pass

    verify = SessionLocal()
    try:
        assert verify.scalar(
            select(Customer).where(
                Customer.salon_id == salon_id,
                Customer.id == customer_id,
            )
        )
        assert verify.scalar(
            select(Booking).where(
                Booking.salon_id == salon_id,
                Booking.id == booking_id,
            )
        )
    finally:
        verify.close()
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


def test_booking_failure_rolls_back_new_customer() -> None:
    phone = f"+7702{uuid.uuid4().int % 10_000_000:07d}"
    as_of = datetime(2026, 6, 4, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 6, 4, 10, 0, tzinfo=UTC)

    gen = get_db()
    session = next(gen)
    salon, _staff, service = _seed_bookable_salon(session)
    customer = CustomerService(session).resolve_public_customer(
        salon_id=salon.id,
        data=PublicCustomerResolveData(full_name="Rollback Guest", phone=phone),
    )

    exc: BookingNotFoundError | None = None
    try:
        BookingService(session).create_booking(
            salon_id=salon.id,
            customer_id=customer.customer_id,
            staff_id=uuid.uuid4(),
            service_id=service.id,
            requested_service_start=service_start,
            source="admin",
            status="confirmed",
            as_of=as_of,
        )
    except BookingNotFoundError as err:
        exc = err

    assert exc is not None
    with pytest.raises(BookingNotFoundError):
        gen.throw(exc)

    verify = SessionLocal()
    try:
        assert (
            verify.scalar(
                select(Customer).where(
                    Customer.salon_id == salon.id,
                    Customer.phone == phone,
                )
            )
            is None
        )
    finally:
        verify.close()
        cleanup = SessionLocal()
        try:
            cleanup.execute(delete(WorkingHour).where(WorkingHour.salon_id == salon.id))
            cleanup.execute(delete(Service).where(Service.salon_id == salon.id))
            cleanup.execute(delete(Staff).where(Staff.salon_id == salon.id))
            cleanup.execute(delete(Salon).where(Salon.id == salon.id))
            cleanup.commit()
        finally:
            cleanup.close()


def test_overlap_integrity_error_still_booking_overlap(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    as_of = datetime(2026, 6, 5, 8, 0, tzinfo=UTC)
    requested = datetime(2026, 6, 5, 10, 0, tzinfo=UTC)
    customer = CustomerService(db_session).resolve_public_customer(
        salon_id=salon.id,
        data=PublicCustomerResolveData(full_name="Overlap", phone="+77009998877"),
    )
    booking_svc = BookingService(db_session)
    booking_svc.create_booking(
        salon_id=salon.id,
        customer_id=customer.customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=requested,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )
    other = CustomerService(db_session).resolve_public_customer(
        salon_id=salon.id,
        data=PublicCustomerResolveData(full_name="Other", phone="+77009998878"),
    )
    with patch.object(
        booking_svc._availability,
        "is_occupied_interval_available",
        return_value=True,
    ):
        with pytest.raises(BookingOverlapError):
            booking_svc.create_booking(
                salon_id=salon.id,
                customer_id=other.customer_id,
                staff_id=staff.id,
                service_id=service.id,
                requested_service_start=requested,
                source="admin",
                status="confirmed",
                as_of=as_of,
            )
