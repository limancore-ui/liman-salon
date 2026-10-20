from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services.admin_notifications.repository import AdminNotificationRepository

SALON_ID = uuid.uuid4()
RECIPIENT_ID = uuid.uuid4()
EVENT_ID = uuid.uuid4()


def _compiled_sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect())).lower()


def test_recipient_query_is_scoped_to_active_owner_and_admin_memberships() -> None:
    session = MagicMock()
    owner_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    session.scalars.return_value.all.return_value = [owner_id, admin_id]
    repository = AdminNotificationRepository(session)

    recipients = repository.list_owner_admin_user_ids(SALON_ID)

    statement = session.scalars.call_args.args[0]
    sql = _compiled_sql(statement)
    assert recipients == [owner_id, admin_id]
    assert "salon_users.salon_id =" in sql
    assert "salon_users.is_active is true" in sql
    assert "salon_users.role in" in sql
    assert SALON_ID in statement.compile().params.values()
    assert ["owner", "admin"] in statement.compile().params.values()


@pytest.mark.parametrize(
    "method_name",
    [
        "list_for_recipient",
        "count_unread_for_recipient",
        "list_since_id",
        "mark_all_read",
        "mark_read",
    ],
)
def test_notification_queries_keep_tenant_and_history_filters(
    method_name: str,
) -> None:
    session = MagicMock()
    session.execute.return_value.all.return_value = []
    session.execute.return_value.rowcount = 0
    session.scalar.return_value = 0
    repository = AdminNotificationRepository(session)

    if method_name == "list_for_recipient":
        repository.list_for_recipient(
            salon_id=SALON_ID,
            recipient_user_id=RECIPIENT_ID,
            limit=50,
            offset=0,
        )
        statement = session.execute.call_args.args[0]
    elif method_name == "count_unread_for_recipient":
        repository.count_unread_for_recipient(
            salon_id=SALON_ID,
            recipient_user_id=RECIPIENT_ID,
        )
        statement = session.scalar.call_args.args[0]
    elif method_name == "list_since_id":
        repository.list_since_id(
            salon_id=SALON_ID,
            recipient_user_id=RECIPIENT_ID,
            after_id=None,
        )
        statement = session.execute.call_args.args[0]
    elif method_name == "mark_all_read":
        repository.mark_all_read(
            salon_id=SALON_ID,
            recipient_user_id=RECIPIENT_ID,
            read_at=datetime.now(timezone.utc),
        )
        statement = session.execute.call_args.args[0]
    else:
        repository.mark_read(
            salon_id=SALON_ID,
            recipient_user_id=RECIPIENT_ID,
            event_id=EVENT_ID,
            read_at=datetime.now(timezone.utc),
        )
        statement = session.execute.call_args.args[0]

    sql = _compiled_sql(statement)
    params = statement.compile().params
    param_values = list(params.values())
    assert "admin_notification_events.salon_id =" in sql
    assert "admin_notification_events.recipient_user_id =" in sql
    assert "admin_notification_events.event_type in" in sql
    assert "bookings.source =" in sql
    assert "public_booking_pending" in str(param_values)
    assert "public_booking_confirmed" in str(param_values)
    assert "public" in param_values
    where_clause = getattr(statement, "whereclause", None)
    assert where_clause is not None
    where_sql = str(where_clause).lower()
    assert "bookings.status" not in where_sql
    if method_name in {"count_unread_for_recipient", "mark_all_read", "mark_read"}:
        assert "admin_notification_events.read_at is null" in where_sql
    else:
        assert "admin_notification_events.read_at" not in where_sql
    if method_name == "mark_read":
        assert EVENT_ID in param_values
        assert SALON_ID in param_values
        assert RECIPIENT_ID in param_values
        assert uuid.uuid4() not in param_values
