"""Malformed salon.settings from DB read path must not surface as HTTP 500."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_booking_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.booking.service import BookingService

from tests.api.conftest import FIXED_AS_OF, SALON_ID

CUSTOMER_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SERVICE_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AUTH_NOW = datetime.now(timezone.utc)


def test_admin_pending_create_malformed_salon_settings_422() -> None:
    """Repository returns invalid JSONB; hold resolve raises SalonSettingsError -> 422."""
    mock_session = MagicMock()
    mock_session.scalar.return_value = {
        "v": 1,
        "booking": {"public_hold_seconds": -1},
    }

    app = create_app()
    app.dependency_overrides[get_booking_service] = lambda: BookingService(mock_session)
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_ID,
        name="Salon",
        slug="salon",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=SALON_ID,
        user_id=USER_ID,
        role="owner",
        is_active=True,
    )
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=AUTH_NOW)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json={
                "customer_id": str(CUSTOMER_ID),
                "staff_id": str(STAFF_ID),
                "service_id": str(SERVICE_ID),
                "requested_service_start": "2026-09-25T10:00:00+00:00",
                "source": "admin",
                "status": "pending",
            },
        )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert "invalid salon settings" in body["detail"]
