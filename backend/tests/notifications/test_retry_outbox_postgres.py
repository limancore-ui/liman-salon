"""C15 notification retry policy (PostgreSQL integration)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.notification import Notification
from app.db.session import engine
from app.services.notifications.constants import MAX_DELIVERY_ATTEMPTS, retry_backoff_seconds
from app.services.notifications.provider import ProviderSendResult
from app.services.notifications.repository import NotificationRepository
from app.services.notifications.service import NotificationService
from tests.notifications.test_confirm_outbox_postgres import (
    AS_OF,
    _booking_service,
    _insert_pending_booking,
    _notification_count,
    _postgres_available,
    _seed_salon_with_booking_entities,
    db_session,
)

pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL test database not reachable",
)


class _RetryableFailProvider:
    def send(self, *, notification: Notification) -> ProviderSendResult:
        return ProviderSendResult(
            success=False,
            error_message="transient",
            failure_kind="retryable",
        )


class _TerminalFailProvider:
    def send(self, *, notification: Notification) -> ProviderSendResult:
        return ProviderSendResult(
            success=False,
            error_message="bad request",
            failure_kind="terminal",
        )


class _FlakyThenSuccessProvider:
    def __init__(self) -> None:
        self.attempts = 0

    def send(self, *, notification: Notification) -> ProviderSendResult:
        self.attempts += 1
        if self.attempts < 3:
            return ProviderSendResult(
                success=False,
                error_message="transient",
                failure_kind="retryable",
            )
        return ProviderSendResult(success=True, provider_message_id="flaky-ok")


def _confirm_one_notification(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    salon, staff, service, customer = _seed_salon_with_booking_entities(session)
    booking_id = _insert_pending_booking(
        session, salon=salon, staff=staff, service=service, customer=customer
    )
    _booking_service(session).admin_confirm_booking(
        salon_id=salon.id,
        booking_id=booking_id,
        as_of=AS_OF,
    )
    return salon.id, booking_id


def _get_notification(session: Session, booking_id: uuid.UUID) -> Notification:
    row = session.scalar(select(Notification).where(Notification.booking_id == booking_id))
    assert row is not None
    return row


def test_retryable_failure_leaves_pending_with_future_schedule(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_RetryableFailProvider())
    run_at = AS_OF + timedelta(minutes=1)
    assert worker.process_due_pending(as_of=run_at) == 1

    row = _get_notification(db_session, booking_id)
    assert row.status == "pending"
    assert row.attempt_count == 1
    assert row.last_error == "transient"
    expected_delay = retry_backoff_seconds(completed_attempt_count=1)
    assert row.scheduled_for == run_at + timedelta(seconds=expected_delay)
    assert row.sent_at is None


def test_retryable_failure_increments_attempt_count(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_RetryableFailProvider())
    worker.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
    row = _get_notification(db_session, booking_id)
    assert row.attempt_count == 1


def test_retryable_subsequent_attempt_when_due(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_RetryableFailProvider())
    first_run = AS_OF + timedelta(minutes=1)
    worker.process_due_pending(as_of=first_run)
    row = _get_notification(db_session, booking_id)
    assert row.scheduled_for is not None

    second_run = row.scheduled_for
    worker.process_due_pending(as_of=second_run)
    row = _get_notification(db_session, booking_id)
    assert row.attempt_count == 2
    assert row.status == "pending"


def test_retryable_eventual_success(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    provider = _FlakyThenSuccessProvider()
    worker = NotificationService(db_session, provider=provider)

    run_at = AS_OF + timedelta(minutes=1)
    worker.process_due_pending(as_of=run_at)
    row = _get_notification(db_session, booking_id)
    assert row.status == "pending"
    assert row.attempt_count == 1

    run_at = row.scheduled_for
    assert run_at is not None
    worker.process_due_pending(as_of=run_at)
    row = _get_notification(db_session, booking_id)
    assert row.status == "pending"
    assert row.attempt_count == 2

    run_at = row.scheduled_for
    assert run_at is not None
    worker.process_due_pending(as_of=run_at)
    row = _get_notification(db_session, booking_id)
    assert row.status == "sent"
    assert row.attempt_count == 3
    assert row.provider_message_id == "flaky-ok"
    assert provider.attempts == 3


def test_eighth_retryable_failure_marks_failed(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_RetryableFailProvider())
    run_at = AS_OF + timedelta(minutes=1)

    for _ in range(MAX_DELIVERY_ATTEMPTS):
        worker.process_due_pending(as_of=run_at)
        row = _get_notification(db_session, booking_id)
        if row.status == "failed":
            break
        assert row.scheduled_for is not None
        run_at = row.scheduled_for
    else:
        pytest.fail("expected failed after max attempts")

    row = _get_notification(db_session, booking_id)
    assert row.status == "failed"
    assert row.attempt_count == MAX_DELIVERY_ATTEMPTS
    assert row.last_error == "transient"
    assert row.scheduled_for is None

    assert worker.process_due_pending(as_of=run_at + timedelta(days=1)) == 0


def test_terminal_failure_marks_failed_immediately(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_TerminalFailProvider())
    worker.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
    row = _get_notification(db_session, booking_id)
    assert row.status == "failed"
    assert row.attempt_count == 1
    assert row.last_error == "bad request"
    assert row.scheduled_for is None


def test_unclassified_failure_is_terminal(db_session: Session) -> None:
    class _UnknownFailProvider:
        def send(self, *, notification: Notification) -> ProviderSendResult:
            return ProviderSendResult(success=False, error_message="provider down")

    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_UnknownFailProvider())
    worker.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
    row = _get_notification(db_session, booking_id)
    assert row.status == "failed"
    assert row.attempt_count == 1


def test_not_due_pending_skipped_until_scheduled_for(db_session: Session) -> None:
    _, booking_id = _confirm_one_notification(db_session)
    worker = NotificationService(db_session, provider=_RetryableFailProvider())
    first_run = AS_OF + timedelta(minutes=1)
    worker.process_due_pending(as_of=first_run)
    row = _get_notification(db_session, booking_id)
    assert row.scheduled_for is not None

    too_early = row.scheduled_for - timedelta(seconds=1)
    assert worker.process_due_pending(as_of=too_early) == 0
    row = _get_notification(db_session, booking_id)
    assert row.attempt_count == 1

    worker.process_due_pending(as_of=row.scheduled_for)
    row = _get_notification(db_session, booking_id)
    assert row.attempt_count == 2


def test_skip_locked_allows_other_rows_while_one_locked() -> None:
    setup_conn = engine.connect()
    setup_trans = setup_conn.begin()
    setup_session = Session(bind=setup_conn, join_transaction_mode="create_savepoint")
    booking_a: uuid.UUID
    booking_b: uuid.UUID
    try:
        salon_a, staff_a, service_a, customer_a = _seed_salon_with_booking_entities(
            setup_session
        )
        booking_a = _insert_pending_booking(
            setup_session,
            salon=salon_a,
            staff=staff_a,
            service=service_a,
            customer=customer_a,
        )
        _booking_service(setup_session).admin_confirm_booking(
            salon_id=salon_a.id,
            booking_id=booking_a,
            as_of=AS_OF,
        )

        salon_b, staff_b, service_b, customer_b = _seed_salon_with_booking_entities(
            setup_session
        )
        booking_b = _insert_pending_booking(
            setup_session,
            salon=salon_b,
            staff=staff_b,
            service=service_b,
            customer=customer_b,
        )
        _booking_service(setup_session).admin_confirm_booking(
            salon_id=salon_b.id,
            booking_id=booking_b,
            as_of=AS_OF,
        )
        setup_trans.commit()
    finally:
        setup_session.close()
        setup_conn.close()

    connection_a = engine.connect()
    trans_a = connection_a.begin()
    session_a = Session(bind=connection_a, join_transaction_mode="create_savepoint")
    connection_b = engine.connect()
    trans_b = connection_b.begin()
    session_b = Session(bind=connection_b, join_transaction_mode="create_savepoint")

    try:
        repo_a = NotificationRepository(session_a)
        locked_batch = repo_a.list_due_pending_for_update(
            as_of=AS_OF + timedelta(minutes=1),
            limit=1,
        )
        assert len(locked_batch) == 1
        locked_booking_id = locked_batch[0].booking_id

        worker_b = NotificationService(session_b)
        processed = worker_b.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
        assert processed == 1
        trans_b.commit()

        row_b = session_b.scalar(
            select(Notification).where(Notification.booking_id == booking_b)
        )
        row_a = session_b.scalar(
            select(Notification).where(Notification.booking_id == booking_a)
        )
        sent = [r for r in (row_a, row_b) if r is not None and r.status == "sent"]
        pending = [r for r in (row_a, row_b) if r is not None and r.status == "pending"]
        assert len(sent) == 1
        assert len(pending) == 1
        assert sent[0].booking_id != locked_booking_id
    finally:
        session_b.close()
        connection_b.close()
        session_a.close()
        trans_a.rollback()
        connection_a.close()

        cleanup_conn = engine.connect()
        cleanup_trans = cleanup_conn.begin()
        cleanup = Session(bind=cleanup_conn)
        try:
            cleanup.execute(
                text(
                    "DELETE FROM notifications WHERE booking_id IN (:a, :b)"
                ),
                {"a": booking_a, "b": booking_b},
            )
            cleanup_trans.commit()
        finally:
            cleanup.close()
            cleanup_conn.close()


def test_retry_processing_is_tenant_scoped(db_session: Session) -> None:
    salon_a, staff_a, service_a, customer_a = _seed_salon_with_booking_entities(db_session)
    booking_a = _insert_pending_booking(
        db_session,
        salon=salon_a,
        staff=staff_a,
        service=service_a,
        customer=customer_a,
    )
    salon_b, staff_b, service_b, customer_b = _seed_salon_with_booking_entities(db_session)
    booking_b = _insert_pending_booking(
        db_session,
        salon=salon_b,
        staff=staff_b,
        service=service_b,
        customer=customer_b,
    )
    svc = _booking_service(db_session)
    svc.admin_confirm_booking(salon_id=salon_a.id, booking_id=booking_a, as_of=AS_OF)
    svc.admin_confirm_booking(salon_id=salon_b.id, booking_id=booking_b, as_of=AS_OF)

    worker = NotificationService(db_session, provider=_RetryableFailProvider())
    run_at = AS_OF + timedelta(minutes=1)
    assert worker.process_due_pending(as_of=run_at) == 2

    row_a = _get_notification(db_session, booking_a)
    row_b = _get_notification(db_session, booking_b)
    assert row_a.salon_id == salon_a.id
    assert row_b.salon_id == salon_b.id
    assert row_a.status == "pending"
    assert row_b.status == "pending"
    assert row_a.attempt_count == 1
    assert row_b.attempt_count == 1


def test_retryable_delivery_rolls_back_with_transaction() -> None:
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        _, booking_id = _confirm_one_notification(session)
        worker = NotificationService(session, provider=_RetryableFailProvider())
        worker.process_due_pending(as_of=AS_OF + timedelta(minutes=1))
        assert _notification_count(session) == 1
        row = _get_notification(session, booking_id)
        assert row.status == "pending"
        assert row.attempt_count == 1
    finally:
        trans.rollback()
        session.close()
        connection.close()

    verify_conn = engine.connect()
    verify = Session(bind=verify_conn)
    try:
        count_for_booking = verify.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.booking_id == booking_id)
        )
        assert count_for_booking == 0
    finally:
        verify.close()
        verify_conn.close()


def test_backoff_seconds_formula() -> None:
    assert retry_backoff_seconds(completed_attempt_count=1) == 60
    assert retry_backoff_seconds(completed_attempt_count=2) == 120
    assert retry_backoff_seconds(completed_attempt_count=3) == 240
    assert retry_backoff_seconds(completed_attempt_count=7) == 3600
    assert retry_backoff_seconds(completed_attempt_count=8) == 3600
