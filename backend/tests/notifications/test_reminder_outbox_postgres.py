"""C16 booking reminder 2h outbox (PostgreSQL integration)."""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.notification import Notification
from app.db.models.staff_service import StaffService
from app.db.models.working_hour import WorkingHour
from app.db.session import engine
from app.services.notifications.constants import (
    TEMPLATE_BOOKING_CONFIRMED,
    TEMPLATE_BOOKING_REMINDER_2H,
)
from app.services.notifications.repository import NotificationRepository
from app.services.notifications.service import NotificationService
from tests.notifications.pg_helpers import (
    AS_OF,
    SLOT_END,
    SLOT_START,
    booking_service,
    insert_pending_booking,
    notification_count,
    postgres_available,
    seed_salon_with_booking_entities,
)

UTC = timezone.utc
REMINDER_DUE = SLOT_START - timedelta(hours=2)

pytestmark = pytest.mark.skipif(
    not postgres_available(),
    reason="PostgreSQL test database not reachable",
)


def _seed_bookable_salon_with_buffer(
    session: Session,
    *,
    buffer_before_minutes: int,
) -> tuple:
    salon, staff, service, customer = seed_salon_with_booking_entities(session)
    service.buffer_before_minutes = buffer_before_minutes
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
    session.add(
        StaffService(
            salon_id=salon.id,
            staff_id=staff.id,
            service_id=service.id,
        )
    )
    session.flush()
    return salon, staff, service, customer


def _reminder_row(session: Session, booking_id: uuid.UUID) -> Notification | None:
    return session.scalar(
        select(Notification).where(
            Notification.booking_id == booking_id,
            Notification.template_key == TEMPLATE_BOOKING_REMINDER_2H,
        )
    )


def test_confirm_schedules_reminder_at_net_service_start_minus_2h(
    db_session: Session,
) -> None:
    salon, staff, service, customer = _seed_bookable_salon_with_buffer(
        db_session, buffer_before_minutes=15
    )
    occupied_start = SLOT_START - timedelta(minutes=15)
    booking_id = uuid.uuid4()
    db_session.add(
        Booking(
            id=booking_id,
            salon_id=salon.id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            starts_at=occupied_start,
            ends_at=SLOT_END,
            status="pending",
            source="public",
            price_cents=service.price_cents,
            currency_code=salon.currency_code,
            duration_minutes=service.duration_minutes,
            expires_at=AS_OF + timedelta(days=1),
        )
    )
    db_session.flush()

    booking_service(db_session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )

    row = _reminder_row(db_session, booking_id)
    assert row is not None
    assert row.status == "pending"
    assert row.scheduled_for == REMINDER_DUE
    assert datetime.fromisoformat(row.payload["starts_at"]) == SLOT_START


def test_pending_booking_has_no_reminder_until_confirm(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    assert notification_count(db_session) == 0


def test_create_confirmed_enqueues_reminder(db_session: Session) -> None:
    salon, staff, service, customer = _seed_bookable_salon_with_buffer(
        db_session, buffer_before_minutes=0
    )
    svc = booking_service(db_session)
    result = svc.create_booking(
        salon_id=salon.id,
        customer_id=customer.id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=SLOT_START,
        source="admin",
        status="confirmed",
        as_of=AS_OF,
    )
    row = _reminder_row(db_session, result.booking_id)
    assert row is not None
    assert row.scheduled_for == REMINDER_DUE


def test_cancel_skips_pending_reminder(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    svc = booking_service(db_session)
    svc.admin_confirm_booking(salon_id=salon.id, booking_id=booking_id, as_of=AS_OF)
    svc.admin_cancel_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF + timedelta(hours=1),
    )
    row = _reminder_row(db_session, booking_id)
    assert row is not None
    assert row.status == "skipped"
    assert row.scheduled_for is None


def _confirmed_booking_with_reminder(
    session: Session,
) -> tuple:
    salon, staff, service, customer = _seed_bookable_salon_with_buffer(
        session, buffer_before_minutes=0
    )
    svc = booking_service(session)
    created = svc.create_booking(
        salon_id=salon.id,
        customer_id=customer.id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=SLOT_START,
        source="admin",
        status="confirmed",
        as_of=AS_OF,
    )
    row = _reminder_row(session, created.booking_id)
    assert row is not None
    return salon, staff, service, customer, created.booking_id, row


def _assert_single_reminder_row(session: Session, booking_id: uuid.UUID) -> None:
    count = session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.booking_id == booking_id,
            Notification.template_key == TEMPLATE_BOOKING_REMINDER_2H,
        )
    )
    assert count == 1


def _assert_reminder_rescheduled(
    row: Notification,
    *,
    before_id: uuid.UUID,
    new_net_start: datetime,
) -> None:
    assert row.id == before_id
    assert row.status == "pending"
    assert row.scheduled_for == new_net_start - timedelta(hours=2)
    assert datetime.fromisoformat(row.payload["starts_at"]) == new_net_start
    assert row.sent_at is None
    assert row.provider_message_id is None
    assert row.last_error is None
    assert row.attempt_count == 0


def test_reschedule_pending_reminder_syncs_same_row(db_session: Session) -> None:
    salon, staff, _service, _customer, booking_id, before = _confirmed_booking_with_reminder(
        db_session
    )
    assert before.status == "pending"
    before_id = before.id

    new_start = SLOT_START + timedelta(days=1)
    booking_service(db_session).admin_reschedule_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        new_staff_id=staff.id,
        new_service_start=new_start,
        as_of=AS_OF,
    )
    after = _reminder_row(db_session, booking_id)
    assert after is not None
    _assert_reminder_rescheduled(after, before_id=before_id, new_net_start=new_start)
    _assert_single_reminder_row(db_session, booking_id)


def test_reschedule_sent_reminder_resets_to_pending(db_session: Session) -> None:
    salon, staff, _service, _customer, booking_id, before = _confirmed_booking_with_reminder(
        db_session
    )
    before_id = before.id
    before.status = "sent"
    before.sent_at = AS_OF + timedelta(minutes=5)
    before.scheduled_for = None
    before.provider_message_id = "provider-msg-1"
    before.attempt_count = 1
    db_session.flush()

    new_start = SLOT_START + timedelta(days=2)
    booking_service(db_session).admin_reschedule_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        new_staff_id=staff.id,
        new_service_start=new_start,
        as_of=AS_OF,
    )
    after = _reminder_row(db_session, booking_id)
    assert after is not None
    _assert_reminder_rescheduled(after, before_id=before_id, new_net_start=new_start)
    _assert_single_reminder_row(db_session, booking_id)


def test_reschedule_failed_reminder_resets_to_pending(db_session: Session) -> None:
    salon, staff, _service, _customer, booking_id, before = _confirmed_booking_with_reminder(
        db_session
    )
    before_id = before.id
    before.status = "failed"
    before.last_error = "provider timeout"
    before.attempt_count = 7
    before.scheduled_for = None
    db_session.flush()

    new_start = SLOT_START + timedelta(days=3)
    booking_service(db_session).admin_reschedule_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        new_staff_id=staff.id,
        new_service_start=new_start,
        as_of=AS_OF,
    )
    after = _reminder_row(db_session, booking_id)
    assert after is not None
    _assert_reminder_rescheduled(after, before_id=before_id, new_net_start=new_start)
    _assert_single_reminder_row(db_session, booking_id)


def test_reschedule_does_not_pending_reminder_when_booking_not_confirmed(
    db_session: Session,
) -> None:
    salon, staff, service, customer = _seed_bookable_salon_with_buffer(
        db_session, buffer_before_minutes=0
    )
    svc = booking_service(db_session)
    created = svc.create_booking(
        salon_id=salon.id,
        customer_id=customer.id,
        staff_id=staff.id,
        service_id=service.id,
        requested_service_start=SLOT_START,
        source="admin",
        status="confirmed",
        as_of=AS_OF,
    )
    row = _reminder_row(db_session, created.booking_id)
    assert row is not None
    row.status = "sent"
    row.sent_at = AS_OF
    row.scheduled_for = None
    row.provider_message_id = "old-msg"
    db_session.flush()

    booking = db_session.get(Booking, created.booking_id)
    assert booking is not None
    booking.status = "pending"
    db_session.flush()

    new_start = SLOT_START + timedelta(days=1)
    svc.admin_reschedule_booking(
        salon_id=salon.id,
        booking_id=created.booking_id,
        new_staff_id=staff.id,
        new_service_start=new_start,
        as_of=AS_OF,
    )
    after = _reminder_row(db_session, created.booking_id)
    assert after is not None
    assert after.status == "sent"
    assert after.sent_at == AS_OF
    assert after.provider_message_id == "old-msg"
    _assert_single_reminder_row(db_session, created.booking_id)


def test_send_time_skip_when_booking_no_longer_confirmed(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    svc = booking_service(db_session)
    svc.admin_confirm_booking(salon_id=salon.id, booking_id=booking_id, as_of=AS_OF)
    svc.admin_cancel_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF + timedelta(minutes=30),
    )
    row = _reminder_row(db_session, booking_id)
    assert row is not None
    assert row.status == "skipped"

    row.status = "pending"
    row.scheduled_for = REMINDER_DUE
    confirm = db_session.scalar(
        select(Notification).where(
            Notification.booking_id == booking_id,
            Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
        )
    )
    assert confirm is not None
    confirm.status = "sent"
    confirm.scheduled_for = None
    db_session.flush()

    worker = NotificationService(db_session)
    assert worker.process_due_pending(as_of=REMINDER_DUE) >= 1
    db_session.refresh(row)
    assert row.status == "skipped"
    assert row.scheduled_for is None
    assert row.attempt_count == 0


def test_reminder_enqueue_idempotent(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    svc = booking_service(db_session)
    svc.admin_confirm_booking(salon_id=salon.id, booking_id=booking_id, as_of=AS_OF)
    booking = db_session.get(Booking, booking_id)
    assert booking is not None
    notifications = NotificationService(db_session)
    first = notifications.enqueue_booking_reminder_2h(salon_id=salon.id, booking=booking)
    second = notifications.enqueue_booking_reminder_2h(salon_id=salon.id, booking=booking)
    assert first is not None and second is not None
    assert first.id == second.id
    repo = NotificationRepository(db_session)
    assert repo.get_reminder_notification(salon.id, booking_id) is not None
