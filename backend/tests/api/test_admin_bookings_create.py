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
from app.services.booking.service import BookingService
from app.services.booking.types import CreateBookingResult

from tests.api.conftest import FIXED_AS_OF

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CUSTOMER_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SERVICE_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
NOW = datetime.now(timezone.utc)


def _booking_payload(**overrides: object) -> dict:
    base = {
        "customer_id": str(CUSTOMER_ID),
        "staff_id": str(STAFF_ID),
        "service_id": str(SERVICE_ID),
        "requested_service_start": "2026-09-25T10:00:00+00:00",
        "source": "admin",
        "status": "confirmed",
    }
    base.update(overrides)
    return base


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
        timezone="UTC",
        currency_code="KZT",
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
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_booking, headers


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_create_booking_owner_admin_passes_context(role: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    booking_id = uuid.uuid4()
    mock_booking.create_booking.return_value = CreateBookingResult(
        booking_id=booking_id,
        starts_at=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
        status="confirmed",
    )
    try:
        response = client.post(
            f"/api/v1/salons/{SALON_A}/bookings",
            headers=headers,
            json=_booking_payload(),
        )
        assert response.status_code == 201
        kwargs = mock_booking.create_booking.call_args.kwargs
        assert kwargs["salon_id"] == SALON_A
        assert kwargs["source"] == "admin"
        assert kwargs["created_by_user_id"] == USER_ID
    finally:
        client.close()


def test_create_booking_unauthenticated_401() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_A}/bookings",
            json=_booking_payload(),
        )
        assert response.status_code == 401


def test_create_booking_missing_membership_403() -> None:
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
            f"/api/v1/salons/{SALON_A}/bookings",
            headers={"Authorization": f"Bearer {token}"},
            json=_booking_payload(),
        )
    assert response.status_code == 403
    assert response.json()["code"] == "salon_access_denied"
    mock_booking.create_booking.assert_not_called()


def test_create_booking_cross_tenant_403() -> None:
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
            f"/api/v1/salons/{SALON_B}/bookings",
            headers={"Authorization": f"Bearer {token}"},
            json=_booking_payload(),
        )
    assert response.status_code == 403
    mock_booking.create_booking.assert_not_called()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_create_booking_forbidden_for_non_admin(role: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings",
        headers=headers,
        json=_booking_payload(),
    )
    assert response.status_code == 403
    mock_booking.create_booking.assert_not_called()
    client.close()
