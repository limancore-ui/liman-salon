from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_admin_notification_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.admin_notifications.service import AdminNotificationService
from app.services.admin_notifications.types import AdminNotificationRow

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
    salon_active: bool = True,
) -> tuple[TestClient, MagicMock, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )

    def _salon_lookup(requested_id: uuid.UUID):
        if requested_id == salon_id and salon_active:
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

    mock_admin = MagicMock(spec=AdminNotificationService)
    mock_admin.list_notifications.return_value = [
        AdminNotificationRow(
            id=uuid.uuid4(),
            event_type="public_booking_pending",
            booking_id=uuid.uuid4(),
            created_at=NOW,
            read_at=None,
            booking_starts_at=NOW,
            customer_name="Guest",
            service_name="Cut",
            staff_name="Stylist",
        )
    ]
    mock_admin.unread_count.return_value = 1
    app.dependency_overrides[get_admin_notification_service] = lambda: mock_admin

    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    headers = {"Authorization": f"Bearer {token}"}
    return TestClient(app), mock_admin, headers


def test_list_requires_owner_or_admin() -> None:
    client, _, headers = _auth_app(role="staff")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/admin-notifications",
        headers=headers,
    )
    assert response.status_code == 403


def test_list_ok_for_owner() -> None:
    client, mock_admin, headers = _auth_app(role="owner")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/admin-notifications",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["unread_count"] == 1
    assert len(data["items"]) == 1
    mock_admin.list_notifications.assert_called_once()


def test_cross_salon_path_denied_when_salon_not_found() -> None:
    client, _, headers = _auth_app(role="owner", salon_id=SALON_A)
    response = client.get(
        f"/api/v1/salons/{SALON_B}/admin-notifications",
        headers=headers,
    )
    assert response.status_code == 404
