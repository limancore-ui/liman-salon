"""PostgreSQL integration tests for in-app admin notification events."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models.admin_notification_event import AdminNotificationEvent
from app.db.models.booking import Booking
from app.db.models.salon import Salon
from app.db.models.salon_user import SalonUser
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.user import User
from app.db.models.working_hour import WorkingHour
from app.db.session import SessionLocal, engine
from app.services.admin_notifications.service import AdminNotificationService
from app.services.booking.service import BookingService
from app.services.public_booking.service import PublicBookingService

UTC = timezone.utc


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _admin_events_table_present() -> bool:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = 'admin_notification_events'"
                )
            ).first()
            return row is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available() or not _admin_events_table_present(),
    reason="PostgreSQL with admin_notification_events migration required",
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


def _seed_salon_with_members(
    session: Session,
) -> tuple[Salon, Staff, Service, User, User, User]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Notify Salon {suffix}",
        slug=f"notify-salon-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()

    for day in range(7):
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

    owner = User(
        email=f"owner-{suffix}@example.com",
        full_name="Owner",
        password_hash=hash_password("secret"),
        is_active=True,
    )
    admin = User(
        email=f"admin-{suffix}@example.com",
        full_name="Admin",
        password_hash=hash_password("secret"),
        is_active=True,
    )
    staff_user = User(
        email=f"staff-{suffix}@example.com",
        full_name="Staff User",
        password_hash=hash_password("secret"),
        is_active=True,
    )
    session.add_all([owner, admin, staff_user])
    session.flush()

    session.add_all(
        [
            SalonUser(salon_id=salon.id, user_id=owner.id, role="owner", is_active=True),
            SalonUser(salon_id=salon.id, user_id=admin.id, role="admin", is_active=True),
            SalonUser(
                salon_id=salon.id,
                user_id=staff_user.id,
                role="staff",
                is_active=True,
            ),
        ]
    )
    session.flush()
    return salon, staff, service, owner, admin, staff_user


def _seed_customer(session: Session, salon_id: uuid.UUID) -> uuid.UUID:
    from app.db.models.customer import Customer

    customer = Customer(
        salon_id=salon_id,
        full_name="Guest",
        phone=f"+7700{uuid.uuid4().int % 10_000_000:07d}",
    )
    session.add(customer)
    session.flush()
    return customer.id


def test_public_booking_creates_owner_admin_events(db_session: Session) -> None:
    salon, staff, service, owner, admin, staff_user = _seed_salon_with_members(
        db_session
    )
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    service_start = datetime(2026, 7, 2, 10, 0, tzinfo=UTC)

    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    result = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=service_start,
        as_of=as_of,
    )

    rows = db_session.scalars(
        select(AdminNotificationEvent).where(
            AdminNotificationEvent.salon_id == salon.id,
            AdminNotificationEvent.booking_id == result.booking_id,
        )
    ).all()
    recipient_ids = {row.recipient_user_id for row in rows}
    assert recipient_ids == {owner.id, admin.id}
    assert staff_user.id not in recipient_ids
    assert len(rows) == 2


def test_admin_created_pending_does_not_enqueue(db_session: Session) -> None:
    salon, staff, service, owner, admin, _staff_user = _seed_salon_with_members(
        db_session
    )
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    expires = as_of + timedelta(hours=1)

    booking_svc = BookingService(
        db_session,
        notifications=MagicMock(),
    )
    admin_svc = AdminNotificationService(db_session)
    result = booking_svc.create_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=datetime(2026, 7, 2, 10, 0, tzinfo=UTC),
        source="admin",
        status="pending",
        as_of=as_of,
        expires_at=expires,
    )
    admin_svc.enqueue_public_booking_pending(
        salon_id=salon.id,
        booking_id=result.booking_id,
    )

    count = db_session.scalar(
        select(AdminNotificationEvent.id).where(
            AdminNotificationEvent.salon_id == salon.id,
            AdminNotificationEvent.booking_id == result.booking_id,
        )
    )
    assert count is None


def test_enqueue_idempotent(db_session: Session) -> None:
    salon, staff, service, owner, admin, _ = _seed_salon_with_members(db_session)
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    result = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 7, 2, 11, 0, tzinfo=UTC),
        as_of=as_of,
    )
    admin_svc = AdminNotificationService(db_session)
    again = admin_svc.enqueue_public_booking_pending(
        salon_id=salon.id,
        booking_id=result.booking_id,
    )
    assert again == 0
    rows = db_session.scalars(
        select(AdminNotificationEvent).where(
            AdminNotificationEvent.booking_id == result.booking_id,
        )
    ).all()
    assert len(rows) == 2


def test_transaction_rollback_removes_events(db_session: Session) -> None:
    salon, staff, service, owner, admin, _ = _seed_salon_with_members(db_session)
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    booking_id: uuid.UUID | None = None
    try:
        with db_session.begin_nested():
            public_svc = PublicBookingService(
                db_session,
                booking_manage_token_pepper="test-pepper",
                admin_notifications=AdminNotificationService(db_session),
            )
            result = public_svc.create_public_booking(
                salon_id=salon.id,
                customer_id=customer_id,
                staff_id=staff.id,
                service_id=service.id,
                service_start=datetime(2026, 7, 2, 12, 0, tzinfo=UTC),
                as_of=as_of,
            )
            booking_id = result.booking_id
            raise RuntimeError("force rollback")
    except RuntimeError:
        pass

    assert booking_id is not None
    rows = db_session.scalars(
        select(AdminNotificationEvent).where(
            AdminNotificationEvent.booking_id == booking_id,
        )
    ).all()
    assert rows == []


def test_stale_when_booking_not_pending(db_session: Session) -> None:
    salon, staff, service, owner, admin, _ = _seed_salon_with_members(db_session)
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    result = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 7, 2, 14, 0, tzinfo=UTC),
        as_of=as_of,
    )
    booking = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == result.booking_id,
        )
    )
    assert booking is not None
    booking.status = "confirmed"
    db_session.flush()

    admin_svc = AdminNotificationService(db_session)
    listed = admin_svc.list_notifications(
        salon_id=salon.id,
        recipient_user_id=owner.id,
        limit=50,
        offset=0,
    )
    assert listed == []
    assert admin_svc.unread_count(salon_id=salon.id, recipient_user_id=owner.id) == 0


def test_cross_tenant_isolation(db_session: Session) -> None:
    salon_a, staff_a, service_a, owner_a, _, _ = _seed_salon_with_members(db_session)
    salon_b, staff_b, service_b, owner_b, _, _ = _seed_salon_with_members(db_session)
    customer_a = _seed_customer(db_session, salon_a.id)
    customer_b = _seed_customer(db_session, salon_b.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)

    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    res_a = public_svc.create_public_booking(
        salon_id=salon_a.id,
        customer_id=customer_a,
        staff_id=staff_a.id,
        service_id=service_a.id,
        service_start=datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
        as_of=as_of,
    )
    res_b = public_svc.create_public_booking(
        salon_id=salon_b.id,
        customer_id=customer_b,
        staff_id=staff_b.id,
        service_id=service_b.id,
        service_start=datetime(2026, 7, 3, 11, 0, tzinfo=UTC),
        as_of=as_of,
    )

    admin_svc = AdminNotificationService(db_session)
    list_a = admin_svc.list_notifications(
        salon_id=salon_a.id,
        recipient_user_id=owner_a.id,
        limit=50,
        offset=0,
    )
    assert len(list_a) == 1
    assert list_a[0].booking_id == res_a.booking_id

    list_b_for_a_owner = admin_svc.list_notifications(
        salon_id=salon_b.id,
        recipient_user_id=owner_a.id,
        limit=50,
        offset=0,
    )
    assert list_b_for_a_owner == []


def test_list_since_returns_public_pending_for_stream(db_session: Session) -> None:
    salon, staff, service, owner, _, _ = _seed_salon_with_members(db_session)
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    result = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 7, 2, 15, 0, tzinfo=UTC),
        as_of=as_of,
    )

    admin_svc = AdminNotificationService(db_session)
    streamed = admin_svc.list_since(
        salon_id=salon.id,
        recipient_user_id=owner.id,
        after_id=None,
        limit=20,
    )
    assert len(streamed) == 1
    assert streamed[0].booking_id == result.booking_id
    assert streamed[0].event_type == "public_booking_pending"


def test_list_since_after_id_cursor_no_gap_no_replay(db_session: Session) -> None:
    salon, staff, service, owner, _, _ = _seed_salon_with_members(db_session)
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    first = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 7, 2, 16, 0, tzinfo=UTC),
        as_of=as_of,
    )
    second = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 7, 2, 17, 0, tzinfo=UTC),
        as_of=as_of,
    )
    event_rows = db_session.scalars(
        select(AdminNotificationEvent).where(
            AdminNotificationEvent.salon_id == salon.id,
            AdminNotificationEvent.recipient_user_id == owner.id,
        )
    ).all()
    assert len(event_rows) == 2
    by_booking = {row.booking_id: row for row in event_rows}
    by_booking[first.booking_id].created_at = as_of
    by_booking[second.booking_id].created_at = as_of + timedelta(seconds=1)
    db_session.flush()

    admin_svc = AdminNotificationService(db_session)
    initial = admin_svc.list_since(
        salon_id=salon.id,
        recipient_user_id=owner.id,
        after_id=None,
        limit=20,
    )
    assert len(initial) == 2
    assert {row.booking_id for row in initial} == {
        first.booking_id,
        second.booking_id,
    }
    assert initial[0].created_at <= initial[1].created_at

    after_first = admin_svc.list_since(
        salon_id=salon.id,
        recipient_user_id=owner.id,
        after_id=initial[0].id,
        limit=20,
    )
    assert len(after_first) == 1
    assert after_first[0].booking_id == initial[1].booking_id
    assert after_first[0].id != initial[0].id

    after_second = admin_svc.list_since(
        salon_id=salon.id,
        recipient_user_id=owner.id,
        after_id=initial[1].id,
        limit=20,
    )
    assert after_second == []


def test_list_since_empty_when_booking_no_longer_pending(db_session: Session) -> None:
    salon, staff, service, owner, _, _ = _seed_salon_with_members(db_session)
    customer_id = _seed_customer(db_session, salon.id)
    as_of = datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    public_svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        admin_notifications=AdminNotificationService(db_session),
    )
    result = public_svc.create_public_booking(
        salon_id=salon.id,
        customer_id=customer_id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 7, 2, 18, 0, tzinfo=UTC),
        as_of=as_of,
    )
    booking = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == result.booking_id,
        )
    )
    assert booking is not None
    booking.status = "confirmed"
    db_session.flush()

    admin_svc = AdminNotificationService(db_session)
    assert (
        admin_svc.list_since(
            salon_id=salon.id,
            recipient_user_id=owner.id,
            after_id=None,
            limit=20,
        )
        == []
    )
