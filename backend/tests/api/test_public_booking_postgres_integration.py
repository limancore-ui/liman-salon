"""Real PostgreSQL HTTP E2E for public booking happy path (no service mocks)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_as_of, get_db
from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.notification import Notification
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.core.config import get_settings
from app.main import create_app
from app.db.session import engine
from app.services.booking.manage_token import verify_manage_token
from app.services.notifications.constants import (
    TEMPLATE_BOOKING_CONFIRMED,
    TEMPLATE_BOOKING_REMINDER_2H,
)
from app.services.notifications.service import NotificationService
from app.services.public_booking.service import PublicBookingService

UTC = timezone.utc
FIXED_AS_OF = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
DUPLICATE_CONFLICT_CODES = frozenset({"slot_not_available", "booking_overlap"})


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
        name=f"Public E2E {suffix}",
        slug=f"public-e2e-{suffix}",
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


@pytest.fixture
def public_booking_client(db_session: Session) -> TestClient:
    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.clear()


def _availability_params(
    *,
    service_id: uuid.UUID,
    staff_id: uuid.UUID,
    day: date,
) -> dict[str, str]:
    day_str = day.isoformat()
    return {
        "service_id": str(service_id),
        "start_date": day_str,
        "end_date": day_str,
        "staff_id": str(staff_id),
    }


def _first_slot_for_staff(body: dict[str, Any], staff_id: uuid.UUID) -> dict[str, str]:
    staff_key = str(staff_id)
    for row in body["staff"]:
        if row["staff_id"] == staff_key and row["slots"]:
            return row["slots"][0]
    raise AssertionError(f"no availability slots for staff {staff_key}")


def _slot_still_listed(
    body: dict[str, Any],
    *,
    staff_id: uuid.UUID,
    service_start: str,
) -> bool:
    staff_key = str(staff_id)
    for row in body["staff"]:
        if row["staff_id"] != staff_key:
            continue
        return any(slot["service_start"] == service_start for slot in row["slots"])
    return False


def test_public_booking_happy_path_http_postgres(
    db_session: Session,
    public_booking_client: TestClient,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    slug = salon.slug
    base = f"/api/v1/public/salons/{slug}"

    salon_resp = public_booking_client.get(base)
    assert salon_resp.status_code == 200
    salon_body = salon_resp.json()
    assert salon_body["slug"] == slug
    assert salon_body["salon_id"] == str(salon.id)

    services_resp = public_booking_client.get(f"{base}/services")
    assert services_resp.status_code == 200
    services_body = services_resp.json()
    assert services_body["salon_id"] == str(salon.id)
    assert len(services_body["services"]) == 1
    assert services_body["services"][0]["id"] == str(service.id)

    staff_resp = public_booking_client.get(f"{base}/services/{service.id}/staff")
    assert staff_resp.status_code == 200
    staff_body = staff_resp.json()
    assert staff_body["service_id"] == str(service.id)
    assert len(staff_body["staff"]) == 1
    assert staff_body["staff"][0]["id"] == str(staff.id)

    probe_day = date(2026, 8, 2)
    avail_before = public_booking_client.get(
        f"{base}/availability/service",
        params=_availability_params(
            service_id=service.id,
            staff_id=staff.id,
            day=probe_day,
        ),
    )
    assert avail_before.status_code == 200
    slot = _first_slot_for_staff(avail_before.json(), staff.id)
    service_start = slot["service_start"]

    phone_a = f"+7750{uuid.uuid4().int % 10_000_000:07d}"
    booking_payload = {
        "full_name": "E2E Guest",
        "phone": phone_a,
        "service_id": str(service.id),
        "staff_id": str(staff.id),
        "service_start": service_start,
    }
    book_resp = public_booking_client.post(f"{base}/bookings", json=booking_payload)
    assert book_resp.status_code == 201
    book_body = book_resp.json()
    assert book_body["salon_id"] == str(salon.id)
    assert book_body["service_start"] == service_start
    parsed_start = datetime.fromisoformat(service_start.replace("Z", "+00:00"))
    expected_service_end = (
        parsed_start + timedelta(minutes=service.duration_minutes)
    ).isoformat().replace("+00:00", "Z")
    assert book_body["service_end"] == expected_service_end
    booking_id = uuid.UUID(book_body["booking_id"])
    customer_id = uuid.UUID(book_body["customer_id"])

    booking_row = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == booking_id,
        )
    )
    assert booking_row is not None
    assert booking_row.status == "confirmed"
    assert booking_row.confirmed_at is not None
    assert booking_row.expires_at is None
    assert book_body["hold_expires_at"] is None
    assert "hold_expires_at" in book_body
    assert booking_row.source == "public"
    manage_token = book_body["manage_token"]
    assert manage_token
    assert booking_row.manage_token_hash is not None
    assert booking_row.manage_token_hash != manage_token
    assert verify_manage_token(
        manage_token,
        booking_row.manage_token_hash,
        pepper=get_settings().booking_manage_token_pepper,
    )
    assert booking_row.starts_at == parsed_start

    customer_row = db_session.scalar(
        select(Customer).where(
            Customer.salon_id == salon.id,
            Customer.id == customer_id,
        )
    )
    assert customer_row is not None
    assert customer_row.phone == phone_a

    avail_after = public_booking_client.get(
        f"{base}/availability/service",
        params=_availability_params(
            service_id=service.id,
            staff_id=staff.id,
            day=probe_day,
        ),
    )
    assert avail_after.status_code == 200
    assert not _slot_still_listed(
        avail_after.json(),
        staff_id=staff.id,
        service_start=service_start,
    )

    phone_b = f"+7751{uuid.uuid4().int % 10_000_000:07d}"
    dup_resp = public_booking_client.post(
        f"{base}/bookings",
        json={
            **booking_payload,
            "full_name": "Duplicate Guest",
            "phone": phone_b,
        },
    )
    assert dup_resp.status_code == 409
    dup_body = dup_resp.json()
    assert dup_body["code"] in DUPLICATE_CONFLICT_CODES

    booking_count = db_session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.salon_id == salon.id,
            Booking.staff_id == staff.id,
        )
    )
    assert booking_count == 1


def test_public_create_enqueues_confirm_notification_once_when_opted_in(
    db_session: Session,
) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    customer = Customer(
        salon_id=salon.id,
        full_name="Opted In",
        phone="+77001112233",
        whatsapp_opt_in=True,
    )
    db_session.add(customer)
    db_session.flush()
    as_of = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
    notifications = NotificationService(db_session)
    result = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        notifications=notifications,
    ).create_public_booking(
        salon_id=salon.id,
        customer_id=customer.id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 8, 2, 10, 0, tzinfo=UTC),
        as_of=as_of,
    )
    booking = db_session.get(Booking, result.booking_id)
    assert booking is not None
    assert booking.status == "confirmed"

    confirm_rows = db_session.scalars(
        select(Notification).where(
            Notification.salon_id == salon.id,
            Notification.booking_id == result.booking_id,
            Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
        )
    ).all()
    reminder_rows = db_session.scalars(
        select(Notification).where(
            Notification.salon_id == salon.id,
            Notification.booking_id == result.booking_id,
            Notification.template_key == TEMPLATE_BOOKING_REMINDER_2H,
        )
    ).all()
    assert len(confirm_rows) == 1
    assert len(reminder_rows) == 1

    again_confirm = notifications.enqueue_booking_confirmed(
        salon_id=salon.id,
        booking=booking,
        as_of=as_of,
    )
    again_reminder = notifications.enqueue_booking_reminder_2h(
        salon_id=salon.id,
        booking=booking,
    )
    assert again_confirm is not None
    assert again_confirm.id == confirm_rows[0].id
    assert again_reminder is not None
    assert again_reminder.id == reminder_rows[0].id

    confirm_count = db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.booking_id == result.booking_id,
            Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
        )
    )
    reminder_count = db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.booking_id == result.booking_id,
            Notification.template_key == TEMPLATE_BOOKING_REMINDER_2H,
        )
    )
    assert confirm_count == 1
    assert reminder_count == 1


def test_public_create_rolls_back_when_notification_enqueue_raises(
    db_session: Session,
) -> None:
    """Exception during outbox enqueue undoes the booking in the same UOW.

    Uses a nested savepoint to mirror request-session rollback without changing
    production code. The HTTP ``get_db`` override in this module does not commit,
    so this asserts savepoint/UOW rollback rather than a live ``SessionLocal`` commit.
    """
    salon, staff, service = _seed_bookable_salon(db_session)
    customer = Customer(
        salon_id=salon.id,
        full_name="Enqueue Fail",
        phone="+77001112255",
        whatsapp_opt_in=True,
    )
    db_session.add(customer)
    db_session.flush()
    notifications = NotificationService(db_session)
    svc = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        notifications=notifications,
    )

    with pytest.raises(RuntimeError, match="forced reminder enqueue failure"):
        with db_session.begin_nested():
            with patch.object(
                notifications,
                "enqueue_booking_reminder_2h",
                side_effect=RuntimeError("forced reminder enqueue failure"),
            ):
                svc.create_public_booking(
                    salon_id=salon.id,
                    customer_id=customer.id,
                    staff_id=staff.id,
                    service_id=service.id,
                    service_start=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
                    as_of=datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
                )

    booking_count = db_session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.salon_id == salon.id)
    )
    notification_count = db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.salon_id == salon.id)
    )
    assert booking_count == 0
    assert notification_count == 0


def test_public_create_skips_notification_without_opt_in(db_session: Session) -> None:
    salon, staff, service = _seed_bookable_salon(db_session)
    customer = Customer(
        salon_id=salon.id,
        full_name="No Consent",
        phone="+77001112244",
        whatsapp_opt_in=False,
    )
    db_session.add(customer)
    db_session.flush()
    result = PublicBookingService(
        db_session,
        booking_manage_token_pepper="test-pepper",
        notifications=NotificationService(db_session),
    ).create_public_booking(
        salon_id=salon.id,
        customer_id=customer.id,
        staff_id=staff.id,
        service_id=service.id,
        service_start=datetime(2026, 8, 2, 11, 0, tzinfo=UTC),
        as_of=datetime(2026, 8, 1, 8, 0, tzinfo=UTC),
    )
    booking = db_session.get(Booking, result.booking_id)
    assert booking is not None
    assert booking.status == "confirmed"
    assert booking.expires_at is None
    count = db_session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.booking_id == result.booking_id)
    )
    assert count == 0
