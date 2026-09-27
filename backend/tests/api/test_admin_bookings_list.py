from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_booking_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.booking.errors import BookingValidationError
from app.services.booking.service import BookingService
from app.services.booking.types import BookingListRow

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOKING_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime.now(timezone.utc)


def _list_row() -> BookingListRow:
    return BookingListRow(
        id=BOOKING_ID,
        status="confirmed",
        starts_at=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
        duration_minutes=60,
        price_cents=5000,
        customer_name="Jane Doe",
        customer_phone="+77001234567",
        staff_name="Alex",
        service_name="Cut",
        source="admin",
        created_at=NOW,
    )


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
    membership: SimpleNamespace | None = None,
) -> tuple[TestClient, MagicMock, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon_id,
        name="Salon",
        slug="salon",
        is_active=True,
    )
    if membership is None:
        membership = SimpleNamespace(
            salon_id=salon_id,
            user_id=USER_ID,
            role=role,
            is_active=True,
        )
    mock_auth.get_active_membership.return_value = membership
    mock_booking = MagicMock(spec=BookingService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_booking_service] = lambda: mock_booking
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_booking, headers


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_list_bookings_owner_admin(role: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    mock_booking.list_bookings.return_value = [_list_row()]
    try:
        response = client.get(
            f"/api/v1/salons/{SALON_A}/bookings",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == str(BOOKING_ID)
        assert body[0]["customer_name"] == "Jane Doe"
        assert body[0]["starts_at"].endswith("+00:00") or body[0]["starts_at"].endswith("Z")
        mock_booking.list_bookings.assert_called_once()
        assert mock_booking.list_bookings.call_args.kwargs["salon_id"] == SALON_A
    finally:
        client.close()


def test_list_bookings_empty() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.list_bookings.return_value = []
    response = client.get(
        f"/api/v1/salons/{SALON_A}/bookings",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == []
    client.close()


def test_list_bookings_filters() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.list_bookings.return_value = []
    starts_from = "2026-09-01T00:00:00+00:00"
    starts_to = "2026-10-01T00:00:00+00:00"
    response = client.get(
        f"/api/v1/salons/{SALON_A}/bookings",
        headers=headers,
        params={
            "starts_at_from": starts_from,
            "starts_at_to": starts_to,
            "status": "confirmed",
            "staff_id": str(STAFF_ID),
            "limit": 25,
            "offset": 10,
        },
    )
    assert response.status_code == 200
    kwargs = mock_booking.list_bookings.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    assert kwargs["status"] == "confirmed"
    assert kwargs["staff_id"] == STAFF_ID
    assert kwargs["limit"] == 25
    assert kwargs["offset"] == 10
    assert kwargs["starts_at_from"].isoformat().startswith("2026-09-01")
    client.close()


def test_list_bookings_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/bookings").status_code == 401


def test_list_bookings_missing_membership_403() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.list_bookings.reset_mock()
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_A,
        name="Salon",
        slug="salon",
        is_active=True,
    )
    mock_auth.get_active_membership.return_value = None
    mock_booking_svc = MagicMock(spec=BookingService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_booking_service] = lambda: mock_booking_svc
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as c:
        response = c.get(
            f"/api/v1/salons/{SALON_A}/bookings",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "salon_access_denied"
    mock_booking_svc.list_bookings.assert_not_called()
    client.close()


def test_list_bookings_cross_tenant_403() -> None:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B,
        name="Other Salon",
        slug="other",
        is_active=True,
    )
    mock_auth.get_active_membership.return_value = None
    mock_booking = MagicMock(spec=BookingService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_booking_service] = lambda: mock_booking
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_B}/bookings",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    mock_booking.list_bookings.assert_not_called()


def test_list_bookings_no_tenant_leak_in_response() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.list_bookings.return_value = [_list_row()]
    response = client.get(
        f"/api/v1/salons/{SALON_A}/bookings",
        headers=headers,
    )
    assert response.status_code == 200
    item = response.json()[0]
    assert "salon_id" not in item
    client.close()


def test_list_bookings_validation_422() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.list_bookings.side_effect = BookingValidationError("invalid booking status filter")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/bookings",
        headers=headers,
        params={"status": "not-a-status"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()
