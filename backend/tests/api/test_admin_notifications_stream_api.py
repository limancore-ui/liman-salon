from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import admin_notifications as admin_notifications_module
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.admin_notifications.types import AdminNotificationRow

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)
NOTIFICATION_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
BOOKING_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")


def _sample_row(*, row_id: uuid.UUID | None = None) -> AdminNotificationRow:
    return AdminNotificationRow(
        id=row_id or NOTIFICATION_ID,
        event_type="public_booking_pending",
        booking_id=BOOKING_ID,
        created_at=NOW,
        read_at=None,
        booking_starts_at=NOW,
        customer_name="Guest",
        service_name="Cut",
        staff_name="Stylist",
    )


def _auth_headers(*, role: str = "owner", salon_id: uuid.UUID = SALON_A) -> dict[str, str]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )

    def _salon_lookup(requested_id: uuid.UUID):
        if requested_id == salon_id:
            return SimpleNamespace(
                id=salon_id,
                name="Salon",
                slug="salon",
                is_active=True,
                timezone="UTC",
                currency_code="KZT",
            )
        return None

    mock_auth.get_active_salon.side_effect = _salon_lookup
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    return app, {"Authorization": f"Bearer {token}"}


def _mock_request(*, disconnected: bool = False) -> MagicMock:
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=disconnected)
    return request


async def _first_sse_data_event(
    *,
    after_id: uuid.UUID | None = None,
    poll_results: list[list[AdminNotificationRow]] | None = None,
    request: MagicMock | None = None,
) -> tuple[str, MagicMock]:
    mock_session = MagicMock()
    mock_service = MagicMock()
    row = _sample_row()
    results = poll_results if poll_results is not None else [[row]]
    mock_request = request or _mock_request()

    def _list_since(**_kwargs):
        return results.pop(0) if results else []

    mock_service.list_since.side_effect = _list_since

    with (
        patch.object(admin_notifications_module.asyncio, "sleep", new_callable=AsyncMock),
        patch.object(admin_notifications_module, "SessionLocal", return_value=mock_session),
        patch.object(
            admin_notifications_module,
            "AdminNotificationService",
            return_value=mock_service,
        ),
    ):
        gen = admin_notifications_module._sse_notification_stream(
            request=mock_request,
            salon_id=SALON_A,
            recipient_user_id=USER_ID,
            after_id=after_id,
        )
        try:
            while True:
                chunk = await gen.__anext__()
                if chunk.startswith("data: "):
                    return chunk, mock_service
        finally:
            await gen.aclose()


def test_stream_unauthenticated_rejected() -> None:
    client = TestClient(create_app())
    response = client.get(f"/api/v1/salons/{SALON_A}/admin-notifications/stream")
    assert response.status_code == 401


def test_stream_staff_rejected() -> None:
    app, headers = _auth_headers(role="staff")
    client = TestClient(app)
    response = client.get(
        f"/api/v1/salons/{SALON_A}/admin-notifications/stream",
        headers=headers,
    )
    assert response.status_code == 403


def test_stream_cross_salon_path_denied() -> None:
    app, headers = _auth_headers(role="owner", salon_id=SALON_A)
    client = TestClient(app)
    response = client.get(
        f"/api/v1/salons/{SALON_B}/admin-notifications/stream",
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.anyio
async def test_stream_payload_shape_without_sensitive_fields() -> None:
    data_line, mock_service = await _first_sse_data_event()
    assert mock_service.list_since.call_args.kwargs["salon_id"] == SALON_A
    assert mock_service.list_since.call_args.kwargs["recipient_user_id"] == USER_ID

    payload = json.loads(data_line.removeprefix("data: "))
    assert payload["type"] == "notification"
    notification = payload["notification"]
    assert set(notification.keys()) == {
        "id",
        "event_type",
        "booking_id",
        "created_at",
        "read_at",
        "booking_starts_at",
        "customer_name",
        "service_name",
        "staff_name",
    }
    assert "phone" not in notification
    assert "email" not in notification
    assert notification["customer_name"] == "Guest"


@pytest.mark.anyio
async def test_stream_passes_after_id_to_list_since() -> None:
    after_id = uuid.uuid4()
    _, mock_service = await _first_sse_data_event(after_id=after_id)
    assert mock_service.list_since.call_args.kwargs["after_id"] == after_id


@pytest.mark.anyio
async def test_stream_deduplicates_repeated_poll_results() -> None:
    row = _sample_row()
    mock_session = MagicMock()
    mock_service = MagicMock()
    poll_results: list[list[AdminNotificationRow]] = [[row], [row], []]
    mock_service.list_since.side_effect = lambda **_kwargs: (
        poll_results.pop(0) if poll_results else []
    )

    events: list[dict] = []
    with (
        patch.object(admin_notifications_module.asyncio, "sleep", new_callable=AsyncMock),
        patch.object(admin_notifications_module, "SessionLocal", return_value=mock_session),
        patch.object(
            admin_notifications_module,
            "AdminNotificationService",
            return_value=mock_service,
        ),
    ):
        gen = admin_notifications_module._sse_notification_stream(
            request=_mock_request(),
            salon_id=SALON_A,
            recipient_user_id=USER_ID,
            after_id=None,
        )
        try:
            for _ in range(6):
                chunk = await gen.__anext__()
                if chunk.startswith("data: "):
                    events.append(json.loads(chunk.removeprefix("data: ")))
                if len(events) >= 1 and mock_service.list_since.call_count >= 2:
                    break
        finally:
            await gen.aclose()

    assert len(events) == 1
    assert events[0]["notification"]["id"] == str(NOTIFICATION_ID)


@pytest.mark.anyio
async def test_stream_exits_when_client_disconnects_before_poll() -> None:
    mock_request = _mock_request(disconnected=True)
    mock_session = MagicMock()

    with (
        patch.object(admin_notifications_module.asyncio, "sleep", new_callable=AsyncMock),
        patch.object(admin_notifications_module, "SessionLocal", return_value=mock_session),
        patch.object(
            admin_notifications_module,
            "AdminNotificationService",
        ) as mock_service_cls,
    ):
        gen = admin_notifications_module._sse_notification_stream(
            request=mock_request,
            salon_id=SALON_A,
            recipient_user_id=USER_ID,
            after_id=None,
        )
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
        await gen.aclose()

    mock_session.close.assert_not_called()
    mock_service_cls.assert_not_called()


@pytest.mark.anyio
async def test_stream_exits_after_sleep_when_client_disconnects() -> None:
    disconnect_after_sleep = False
    poll_count = 0
    mock_request = MagicMock()

    async def _is_disconnected() -> bool:
        return disconnect_after_sleep

    mock_request.is_disconnected = _is_disconnected
    mock_session = MagicMock()
    mock_service = MagicMock()
    row = _sample_row()

    def _list_since(**_kwargs):
        nonlocal poll_count
        poll_count += 1
        if poll_count == 1:
            return [row]
        return []

    mock_service.list_since.side_effect = _list_since

    with (
        patch.object(admin_notifications_module.asyncio, "sleep", new_callable=AsyncMock),
        patch.object(admin_notifications_module, "SessionLocal", return_value=mock_session),
        patch.object(
            admin_notifications_module,
            "AdminNotificationService",
            return_value=mock_service,
        ),
    ):
        gen = admin_notifications_module._sse_notification_stream(
            request=mock_request,
            salon_id=SALON_A,
            recipient_user_id=USER_ID,
            after_id=None,
        )
        chunk = await gen.__anext__()
        assert chunk.startswith("data: ")
        disconnect_after_sleep = True
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
        await gen.aclose()

    assert poll_count == 1
    assert mock_service.list_since.call_count == 1
    assert mock_session.close.call_count == 1


@pytest.mark.anyio
async def test_stream_session_close_bounded_on_disconnect() -> None:
    disconnect_checks = 0
    mock_request = MagicMock()

    async def _is_disconnected() -> bool:
        nonlocal disconnect_checks
        disconnect_checks += 1
        return disconnect_checks > 2

    mock_request.is_disconnected = _is_disconnected
    mock_session = MagicMock()
    mock_service = MagicMock()
    mock_service.list_since.return_value = []

    with (
        patch.object(admin_notifications_module.asyncio, "sleep", new_callable=AsyncMock),
        patch.object(admin_notifications_module, "SessionLocal", return_value=mock_session),
        patch.object(
            admin_notifications_module,
            "AdminNotificationService",
            return_value=mock_service,
        ),
    ):
        gen = admin_notifications_module._sse_notification_stream(
            request=mock_request,
            salon_id=SALON_A,
            recipient_user_id=USER_ID,
            after_id=None,
        )
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()
        await gen.aclose()

    assert mock_session.close.call_count <= 2
