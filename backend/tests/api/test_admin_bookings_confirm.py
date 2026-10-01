from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_booking_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.service import BookingService
from app.services.booking.types import ConfirmBookingResult

from tests.api.conftest import FIXED_AS_OF

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOKING_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime.now(timezone.utc)
CONFIRMED_AT = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
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
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    mock_booking = MagicMock(spec=BookingService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_booking_service] = lambda: mock_booking
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_booking, headers


def test_admin_confirm_unauthenticated_401() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/confirm",
        )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_admin_confirm_forbidden_for_non_admin(role: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/confirm",
        headers=headers,
    )
    assert response.status_code == 403
    mock_booking.admin_confirm_booking.assert_not_called()
    client.close()


def test_admin_confirm_cross_tenant_403() -> None:
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
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    mock_booking = MagicMock(spec=BookingService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_booking_service] = lambda: mock_booking
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_B}/bookings/{BOOKING_ID}/confirm",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    mock_booking.admin_confirm_booking.assert_not_called()


def test_admin_confirm_booking_not_in_salon_404() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_confirm_booking.side_effect = BookingNotFoundError(
        "booking not found"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/confirm",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    kwargs = mock_booking.admin_confirm_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    assert kwargs["booking_id"] == BOOKING_ID
    assert kwargs["as_of"] == FIXED_AS_OF
    client.close()


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_admin_confirm_success_delegates(role: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    mock_booking.admin_confirm_booking.return_value = ConfirmBookingResult(
        booking_id=BOOKING_ID,
        status="confirmed",
        confirmed_at=CONFIRMED_AT,
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/confirm",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["booking_id"] == str(BOOKING_ID)
    assert body["status"] == "confirmed"
    assert body["confirmed_at"] is not None
    mock_booking.admin_confirm_booking.assert_called_once()
    kwargs = mock_booking.admin_confirm_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    client.close()


def test_admin_confirm_stale_pending_rejected_422() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_confirm_booking.side_effect = BookingValidationError(
        "booking cannot be confirmed in its current status"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/confirm",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()


def test_admin_confirm_already_confirmed_rejected_422() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_confirm_booking.side_effect = BookingValidationError(
        "booking cannot be confirmed in its current status"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/confirm",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()
