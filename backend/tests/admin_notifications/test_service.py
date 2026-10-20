from __future__ import annotations

import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.admin_notifications.constants import (
    EVENT_TYPE_PUBLIC_BOOKING_CONFIRMED,
    EVENT_TYPE_PUBLIC_BOOKING_PENDING,
)
from app.services.admin_notifications.service import AdminNotificationService

SALON_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()


@contextmanager
def _savepoint():
    """Propagate errors after the block, matching Session.begin_nested()."""
    yield


def _service(*, booking: object | None, recipients: list[uuid.UUID]):
    session = MagicMock()
    session.begin_nested.side_effect = _savepoint
    service = AdminNotificationService(session)
    service._bookings = MagicMock()
    service._bookings.get_booking.return_value = booking
    service._repo = MagicMock()
    service._repo.list_owner_admin_user_ids.return_value = recipients
    return service


def test_confirmed_public_booking_notifies_only_selected_salon_recipients() -> None:
    service = _service(
        booking=SimpleNamespace(source="public", status="confirmed"),
        recipients=[OWNER_ID, ADMIN_ID],
    )

    created = service.enqueue_public_booking_confirmed(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
    )

    assert created == 2
    service._bookings.get_booking.assert_called_once_with(SALON_ID, BOOKING_ID)
    service._repo.list_owner_admin_user_ids.assert_called_once_with(SALON_ID)
    assert [call.kwargs for call in service._repo.add_event.call_args_list] == [
        {
            "salon_id": SALON_ID,
            "booking_id": BOOKING_ID,
            "recipient_user_id": OWNER_ID,
            "event_type": EVENT_TYPE_PUBLIC_BOOKING_CONFIRMED,
        },
        {
            "salon_id": SALON_ID,
            "booking_id": BOOKING_ID,
            "recipient_user_id": ADMIN_ID,
            "event_type": EVENT_TYPE_PUBLIC_BOOKING_CONFIRMED,
        },
    ]
    assert service._session.flush.call_count == 2


def test_pending_public_booking_keeps_existing_event_type() -> None:
    service = _service(
        booking=SimpleNamespace(source="public", status="pending"),
        recipients=[OWNER_ID],
    )

    created = service.enqueue_public_booking_pending(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
    )

    assert created == 1
    service._repo.add_event.assert_called_once_with(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
        recipient_user_id=OWNER_ID,
        event_type=EVENT_TYPE_PUBLIC_BOOKING_PENDING,
    )


@pytest.mark.parametrize(
    "booking",
    [
        None,
        SimpleNamespace(source="admin", status="confirmed"),
        SimpleNamespace(source="public", status="pending"),
    ],
)
def test_confirmed_enqueue_ignores_missing_or_ineligible_booking(booking) -> None:
    service = _service(booking=booking, recipients=[OWNER_ID])

    created = service.enqueue_public_booking_confirmed(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
    )

    assert created == 0
    service._repo.list_owner_admin_user_ids.assert_not_called()
    service._repo.add_event.assert_not_called()

def test_duplicate_notification_integrity_error_is_ignored() -> None:
    from sqlalchemy.exc import IntegrityError

    service = _service(
        booking=SimpleNamespace(source="public", status="confirmed"),
        recipients=[OWNER_ID],
    )

    original = SimpleNamespace(
        sqlstate="23505",
        diag=SimpleNamespace(
            constraint_name="uq_admin_notification_events_recipient_booking"
        ),
    )
    service._session.flush.side_effect = IntegrityError(
        "duplicate notification",
        {},
        original,
    )

    created = service.enqueue_public_booking_confirmed(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
    )

    assert created == 0
    service._repo.add_event.assert_called_once()


def test_duplicate_then_success_counts_only_new_events() -> None:
    from sqlalchemy.exc import IntegrityError

    service = _service(
        booking=SimpleNamespace(source="public", status="confirmed"),
        recipients=[OWNER_ID, ADMIN_ID],
    )
    duplicate = IntegrityError(
        "duplicate notification",
        {},
        SimpleNamespace(
            sqlstate="23505",
            diag=SimpleNamespace(
                constraint_name="uq_admin_notification_events_recipient_booking"
            ),
        ),
    )
    service._session.flush.side_effect = [duplicate, None]

    created = service.enqueue_public_booking_confirmed(
        salon_id=SALON_ID,
        booking_id=BOOKING_ID,
    )

    assert created == 1
    assert [call.kwargs["recipient_user_id"] for call in service._repo.add_event.call_args_list] == [
        OWNER_ID,
        ADMIN_ID,
    ]


def _integrity_error(sqlstate: str | None, constraint_name: str | None):
    from sqlalchemy.exc import IntegrityError

    original = SimpleNamespace(
        sqlstate=sqlstate,
        diag=SimpleNamespace(constraint_name=constraint_name),
    )
    return IntegrityError(
        "unrelated integrity error phone=+996555000000 notes=secret token=abc",
        {"database_url": "postgresql://user:secret@db/liman"},
        original,
    )


def test_non_duplicate_integrity_error_is_isolated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = _service(
        booking=SimpleNamespace(source="public", status="confirmed"),
        recipients=[OWNER_ID, ADMIN_ID],
    )
    service._session.flush.side_effect = [
        _integrity_error("23514", "ck_admin_notification_events_event_type"),
        None,
    ]

    with caplog.at_level("WARNING"):
        created = service.enqueue_public_booking_confirmed(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
        )

    assert created == 1
    assert service._repo.add_event.call_count == 2
    assert service._session.flush.call_count == 2
    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "sqlstate=23514" in message
    assert "constraint=ck_admin_notification_events_event_type" in message
    assert f"salon_id={SALON_ID}" in message
    assert f"booking_id={BOOKING_ID}" in message
    assert "unrelated integrity error" not in message
    assert "phone=" not in message
    assert "notes=" not in message
    assert "postgresql://" not in message
    assert "secret" not in message
    assert "token=" not in message
