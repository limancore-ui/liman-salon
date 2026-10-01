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
from app.services.booking.types import (
    CompleteVisitResult,
    NoShowVisitResult,
    StartVisitResult,
)

from tests.api.conftest import FIXED_AS_OF

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOKING_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
NOW = datetime.now(timezone.utc)
COMPLETED_AT = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)


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


@pytest.mark.parametrize(
    "path_suffix,method_name",
    [
        ("start", "admin_start_visit"),
        ("complete", "admin_complete_visit"),
        ("no-show", "admin_mark_no_show"),
    ],
)
def test_admin_visit_unauthenticated_401(path_suffix: str, method_name: str) -> None:
    del method_name
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/{path_suffix}",
        )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "path_suffix,method_name",
    [
        ("start", "admin_start_visit"),
        ("complete", "admin_complete_visit"),
        ("no-show", "admin_mark_no_show"),
    ],
)
@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_admin_visit_forbidden_for_non_admin(
    path_suffix: str,
    method_name: str,
    role: str,
) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/{path_suffix}",
        headers=headers,
    )
    assert response.status_code == 403
    getattr(mock_booking, method_name).assert_not_called()
    client.close()


def test_admin_start_success_delegates() -> None:
    client, mock_booking, headers = _auth_app(role="admin")
    mock_booking.admin_start_visit.return_value = StartVisitResult(
        booking_id=BOOKING_ID,
        status="in_progress",
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/start",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    kwargs = mock_booking.admin_start_visit.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    assert kwargs["booking_id"] == BOOKING_ID
    assert kwargs["as_of"] == FIXED_AS_OF
    client.close()


def test_admin_complete_success_delegates() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_complete_visit.return_value = CompleteVisitResult(
        booking_id=BOOKING_ID,
        status="completed",
        completed_at=COMPLETED_AT,
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/complete",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None
    client.close()


def test_admin_no_show_success_delegates() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_mark_no_show.return_value = NoShowVisitResult(
        booking_id=BOOKING_ID,
        status="no_show",
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/no-show",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_show"
    client.close()


def test_admin_start_cross_tenant_403() -> None:
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
            f"/api/v1/salons/{SALON_B}/bookings/{BOOKING_ID}/start",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    mock_booking.admin_start_visit.assert_not_called()


def test_admin_start_not_found_404() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_start_visit.side_effect = BookingNotFoundError(
        "booking not found"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/start",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    client.close()


def test_admin_start_illegal_status_422() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_start_visit.side_effect = BookingValidationError(
        "booking cannot be started in its current status"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/start",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()


def test_admin_no_show_illegal_status_422() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_mark_no_show.side_effect = BookingValidationError(
        "booking cannot be marked no-show in its current status"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/no-show",
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()
