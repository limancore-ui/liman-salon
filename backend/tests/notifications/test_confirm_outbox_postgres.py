"""C13 confirm notification outbox (PostgreSQL integration)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.notification import Notification
from app.db.session import engine
from app.services.booking.errors import BookingValidationError
from app.services.notifications.constants import (
    CHANNEL_WHATSAPP,
    PROVIDER_STUB,
    TEMPLATE_BOOKING_CONFIRMED,
)
from app.services.notifications.provider import ProviderSendResult
from app.services.notifications.repository import NotificationRepository
from app.services.notifications.service import NotificationService
from tests.notifications.pg_helpers import (
    AS_OF,
    booking_service,
    confirm_idempotency_constraint_present,
    insert_pending_booking,
    notification_count,
    postgres_available,
    seed_salon_with_booking_entities,
)

pytestmark = pytest.mark.skipif(
    not postgres_available(),
    reason="PostgreSQL test database not reachable",
)


def test_confirm_with_phone_and_opt_in_creates_pending_notification(
    db_session: Session,
) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )

    booking_service(db_session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )

    rows = list(
        db_session.scalars(
            select(Notification).where(Notification.salon_id == salon.id)
        )
    )
    assert len(rows) == 2
    row = db_session.scalar(
        select(Notification).where(
            Notification.booking_id == booking_id,
            Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
        )
    )
    assert row is not None
    assert row.status == "pending"
    assert row.salon_id == salon.id
    assert row.booking_id == booking_id
    assert row.customer_id == customer.id
    assert row.template_key == TEMPLATE_BOOKING_CONFIRMED
    assert row.channel == CHANNEL_WHATSAPP
    assert row.provider == PROVIDER_STUB
    assert row.recipient_address == customer.phone


def test_confirm_missing_phone_no_notification(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(
        db_session, phone=None
    )
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )

    result = booking_service(db_session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    assert result.status == "confirmed"
    assert notification_count(db_session) == 0


def test_confirm_whatsapp_opt_in_false_no_notification(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(
        db_session, whatsapp_opt_in=False
    )
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )

    booking_service(db_session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    assert notification_count(db_session) == 0


def test_confirm_and_notification_roll_back_together() -> None:
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    salon, staff, service, customer = seed_salon_with_booking_entities(session)
    booking_id = insert_pending_booking(
        session, salon=salon, staff=staff, service=service, customer=customer
    )
    booking_service(session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    assert notification_count(session) == 2
    trans.rollback()
    session.close()
    connection.close()

    verify_conn = engine.connect()
    verify = Session(bind=verify_conn)
    try:
        assert verify.get(Booking, booking_id) is None
        count_for_booking = verify.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.booking_id == booking_id)
        )
        assert count_for_booking == 0
    finally:
        verify.close()
        verify_conn.close()


def test_enqueue_idempotent_second_call_no_extra_row(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    svc = booking_service(db_session)
    svc.admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    booking = db_session.scalar(
        select(Booking).where(
            Booking.salon_id == salon.id,
            Booking.id == booking_id,
        )
    )
    assert booking is not None
    notifications = NotificationService(db_session)
    first = notifications.enqueue_booking_confirmed(
        salon_id=salon.id, booking=booking, as_of=AS_OF
    )
    second = notifications.enqueue_booking_confirmed(
        salon_id=salon.id, booking=booking, as_of=AS_OF
    )
    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert notification_count(db_session) == 2


@pytest.mark.skipif(
    not confirm_idempotency_constraint_present(),
    reason="Migration 20250924_0018 not applied on test database",
)
def test_unique_constraint_blocks_duplicate_insert(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    db_session.add_all(
        [
            Notification(
                salon_id=salon.id,
                booking_id=booking_id,
                customer_id=customer.id,
                channel=CHANNEL_WHATSAPP,
                template_key=TEMPLATE_BOOKING_CONFIRMED,
                recipient_address="+77001111111",
                payload={},
                status="pending",
                provider=PROVIDER_STUB,
            ),
            Notification(
                salon_id=salon.id,
                booking_id=booking_id,
                customer_id=customer.id,
                channel=CHANNEL_WHATSAPP,
                template_key=TEMPLATE_BOOKING_CONFIRMED,
                recipient_address="+77002222222",
                payload={},
                status="pending",
                provider=PROVIDER_STUB,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_already_confirmed_does_not_enqueue_again(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    svc = booking_service(db_session)
    svc.admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    assert notification_count(db_session) == 2
    with pytest.raises(BookingValidationError, match="cannot be confirmed"):
        svc.admin_confirm_booking(
            salon_id=salon.id,
            booking_id=booking_id,
            as_of=AS_OF + timedelta(hours=1),
        )
    assert notification_count(db_session) == 2


def test_tenant_scoped_confirm_lookup(db_session: Session) -> None:
    salon_a, staff_a, service_a, customer_a = seed_salon_with_booking_entities(
        db_session
    )
    salon_b, staff_b, service_b, customer_b = seed_salon_with_booking_entities(
        db_session
    )
    booking_a = insert_pending_booking(
        db_session,
        salon=salon_a,
        staff=staff_a,
        service=service_a,
        customer=customer_a,
    )
    booking_b = insert_pending_booking(
        db_session,
        salon=salon_b,
        staff=staff_b,
        service=service_b,
        customer=customer_b,
    )
    svc = booking_service(db_session)
    svc.admin_confirm_booking(
        salon_id=salon_a.id, booking_id=booking_a, as_of=AS_OF
    )
    svc.admin_confirm_booking(
        salon_id=salon_b.id, booking_id=booking_b, as_of=AS_OF
    )

    repo = NotificationRepository(db_session)
    assert repo.get_confirm_notification(salon_a.id, booking_a) is not None
    assert repo.get_confirm_notification(salon_a.id, booking_b) is None
    assert repo.get_confirm_notification(salon_b.id, booking_b) is not None


class _FailingProvider:
    def send(self, *, notification: Notification) -> ProviderSendResult:
        return ProviderSendResult(success=False, error_message="provider down")


def test_worker_marks_pending_as_sent(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    booking_service(db_session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    worker = NotificationService(db_session)
    count = worker.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
    assert count == 1
    row = db_session.scalar(
        select(Notification).where(
            Notification.booking_id == booking_id,
            Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
        )
    )
    assert row is not None
    assert row.status == "sent"
    assert row.sent_at == AS_OF + timedelta(minutes=1)
    assert row.attempt_count == 1
    assert row.provider_message_id is not None


def test_worker_provider_failure_marks_failed(db_session: Session) -> None:
    salon, staff, service, customer = seed_salon_with_booking_entities(db_session)
    booking_id = insert_pending_booking(
        db_session, salon=salon, staff=staff, service=service, customer=customer
    )
    booking_service(db_session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    worker = NotificationService(db_session, provider=_FailingProvider())
    worker.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
    row = db_session.scalar(
        select(Notification).where(
            Notification.booking_id == booking_id,
            Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
        )
    )
    assert row is not None
    assert row.status == "failed"
    assert row.attempt_count == 1
    assert row.last_error == "provider down"
    assert row.sent_at is None
