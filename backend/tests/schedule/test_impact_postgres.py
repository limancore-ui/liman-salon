"""PostgreSQL integration tests for schedule impact preview."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, time, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import SessionLocal, engine
from app.services.booking.service import BookingService
from app.services.customer.service import CustomerService, PublicCustomerResolveData
from app.services.schedule.impact import ScheduleImpactService
from app.services.schedule.overlay import (
    StaffServiceDetachChange,
    WorkingHoursUpdateChange,
)

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


def _seed_salon(session: Session) -> tuple[Salon, Staff, Service, WorkingHour]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Impact {suffix}",
        slug=f"impact-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()
    wh = WorkingHour(
        salon_id=salon.id,
        staff_id=None,
        day_of_week=3,
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    session.add(wh)
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
    return salon, staff, service, wh


def _customer(session: Session, salon_id: uuid.UUID) -> uuid.UUID:
    result = CustomerService(session).resolve_public_customer(
        salon_id=salon_id,
        data=PublicCustomerResolveData(
            full_name="Patron",
            phone=f"+7700{uuid.uuid4().int % 10_000_000:07d}",
        ),
    )
    return result.customer_id


def test_working_hours_shrink_marks_confirmed_booking_impacted(
    db_session: Session,
) -> None:
    salon, staff, service, wh = _seed_salon(db_session)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    booking_start = datetime(2026, 8, 6, 16, 0, tzinfo=UTC)  # Thursday (day 3)
    customer_id = _customer(db_session, salon.id)
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=booking_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )
    impact_svc = ScheduleImpactService(db_session)
    result = impact_svc.preview_impact(
        salon_id=salon.id,
        change=WorkingHoursUpdateChange(
            working_hours_id=wh.id,
            end_time=time(15, 0),
        ),
        as_of=as_of,
    )
    assert len(result.all_impacts) == 1
    assert result.all_impacts[0].reasons == ("outside_availability",)


def test_detach_reports_staff_no_longer_performs_service(
    db_session: Session,
) -> None:
    salon, staff, service, _wh = _seed_salon(db_session)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    booking_start = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    customer_id = _customer(db_session, salon.id)
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=booking_start,
        source="admin",
        status="confirmed",
        as_of=as_of,
    )
    result = ScheduleImpactService(db_session).preview_impact(
        salon_id=salon.id,
        change=StaffServiceDetachChange(staff_id=staff.id, service_id=service.id),
        as_of=as_of,
    )
    assert len(result.all_impacts) == 1
    assert "staff_no_longer_performs_service" in result.all_impacts[0].reasons
    booking = db_session.scalar(
        select(Booking).where(Booking.salon_id == salon.id)
    )
    assert booking is not None
    assert booking.status == "confirmed"


def test_past_confirmed_booking_excluded_from_impact_set(
    db_session: Session,
) -> None:
    salon, staff, service, wh = _seed_salon(db_session)
    as_of = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    booking_start = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    customer_id = _customer(db_session, salon.id)
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=booking_start,
        source="admin",
        status="confirmed",
        as_of=datetime(2026, 8, 6, 8, 0, tzinfo=UTC),
    )
    result = ScheduleImpactService(db_session).preview_impact(
        salon_id=salon.id,
        change=WorkingHoursUpdateChange(
            working_hours_id=wh.id,
            end_time=time(9, 0),
        ),
        as_of=as_of,
        horizon_days=1,
    )
    assert result.all_impacts == ()


def test_in_progress_booking_included_when_ends_after_as_of(
    db_session: Session,
) -> None:
    salon, staff, service, wh = _seed_salon(db_session)
    as_of = datetime(2026, 8, 6, 10, 30, tzinfo=UTC)
    booking_start = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    customer_id = _customer(db_session, salon.id)
    created = BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=booking_start,
        source="admin",
        status="confirmed",
        as_of=datetime(2026, 8, 6, 8, 0, tzinfo=UTC),
    )
    BookingService(db_session).admin_start_visit(
        salon_id=salon.id,
        booking_id=created.booking_id,
        as_of=as_of - timedelta(minutes=5),
    )
    result = ScheduleImpactService(db_session).preview_impact(
        salon_id=salon.id,
        change=WorkingHoursUpdateChange(
            working_hours_id=wh.id,
            end_time=time(10, 45),
        ),
        as_of=as_of,
        horizon_days=1,
    )
    assert any(row.is_in_progress for row in result.all_impacts)


def test_expired_pending_hold_not_in_impact_set(db_session: Session) -> None:
    salon, staff, service, _wh = _seed_salon(db_session)
    as_of = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
    # Seeded salon hours are Thursday (day_of_week=3) only.
    booking_start = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
    customer_id = _customer(db_session, salon.id)
    create_as_of = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)
    BookingService(db_session).create_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=booking_start,
        source="public",
        status="pending",
        as_of=create_as_of,
        expires_at=create_as_of + timedelta(hours=1),
    )
    booking = db_session.scalar(select(Booking).where(Booking.salon_id == salon.id))
    assert booking is not None
    booking.expires_at = as_of - timedelta(minutes=1)
    db_session.flush()
    result = ScheduleImpactService(db_session).preview_impact(
        salon_id=salon.id,
        change=StaffServiceDetachChange(staff_id=staff.id, service_id=service.id),
        as_of=as_of,
    )
    assert result.all_impacts == ()


def test_tenant_isolation_other_salon_booking_not_listed(
    db_session: Session,
) -> None:
    salon_a, staff_a, service_a, _ = _seed_salon(db_session)
    salon_b, staff_b, service_b, _ = _seed_salon(db_session)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    start = datetime(2026, 8, 6, 11, 0, tzinfo=UTC)
    for salon, staff, service in (
        (salon_a, staff_a, service_a),
        (salon_b, staff_b, service_b),
    ):
        BookingService(db_session).create_booking(
            salon_id=salon.id,
            customer_id=_customer(db_session, salon.id),
            staff_id=staff.id,
            service_id=service.id,
            requested_service_start=start,
            source="admin",
            status="confirmed",
            as_of=as_of,
        )
    result = ScheduleImpactService(db_session).preview_impact(
        salon_id=salon_a.id,
        change=StaffServiceDetachChange(
            staff_id=staff_a.id,
            service_id=service_a.id,
        ),
        as_of=as_of,
    )
    assert len(result.all_impacts) == 1
    assert result.all_impacts[0].staff_id == staff_a.id


def test_fingerprint_same_across_pagination_offsets(db_session: Session) -> None:
    salon, staff, service, wh = _seed_salon(db_session)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    for hour in (10, 11, 12):
        BookingService(db_session).create_booking(
            salon_id=salon.id,
            customer_id=_customer(db_session, salon.id),
            staff_id=staff.id,
            service_id=service.id,
            requested_service_start=datetime(2026, 8, 6, hour, 0, tzinfo=UTC),
            source="admin",
            status="confirmed",
            as_of=as_of,
        )
    change = WorkingHoursUpdateChange(
        working_hours_id=wh.id,
        end_time=time(9, 30),
    )
    svc = ScheduleImpactService(db_session)
    first = svc.preview_impact(
        salon_id=salon.id,
        change=change,
        as_of=as_of,
        impact_offset=0,
        impact_limit=1,
    )
    second = svc.preview_impact(
        salon_id=salon.id,
        change=change,
        as_of=as_of,
        impact_offset=1,
        impact_limit=1,
    )
    assert first.impact_fingerprint == second.impact_fingerprint
    assert len(first.all_impacts) >= 2
    assert len(first.impacts) == 1
    assert len(second.impacts) == 1
