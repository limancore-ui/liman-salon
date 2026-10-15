"""HTTP mapping for schedule gate contention vs generic schedule errors."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_booking_service, get_schedule_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.schedule.errors import ScheduleBusyError, ScheduleError

from tests.api.conftest import FIXED_AS_OF, SALON_ID

USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AUTH_NOW = datetime.now(timezone.utc)


def _auth_headers_for_app(app) -> dict[str, str]:
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
    return {"Authorization": f"Bearer {token}"}


def test_schedule_busy_error_returns_503_with_retry_after() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = ScheduleBusyError("schedule gate busy")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json={
                "customer_id": "33333333-3333-4333-8333-333333333333",
                "staff_id": "22222222-2222-4222-8222-222222222222",
                "service_id": "44444444-4444-4444-8444-444444444444",
                "requested_service_start": "2026-09-25T10:00:00+00:00",
                "source": "admin",
                "status": "confirmed",
            },
        )

    assert response.status_code == 503
    assert response.headers.get("retry-after") == "2"
    body = response.json()
    assert body["code"] == "schedule_busy"
    assert body["detail"] == "schedule gate busy"


def test_generic_schedule_error_still_returns_422() -> None:
    app = create_app()
    mock_schedule = MagicMock()
    mock_schedule.list_working_hours.side_effect = ScheduleError("schedule unavailable")
    app.dependency_overrides[get_schedule_service] = lambda: mock_schedule
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_ID}/schedule/working-hours",
            headers=headers,
        )

    assert response.status_code == 422
    assert response.json()["code"] == "schedule_error"
