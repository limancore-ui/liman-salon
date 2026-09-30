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
from app.services.booking.errors import (
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)
from app.services.booking.service import BookingService
from app.services.booking.types import RescheduleBookingResult

from tests.api.conftest import FIXED_AS_OF

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOKING_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime.now(timezone.utc)
SERVICE_START = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
SERVICE_END = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)


def _payload(**overrides: object) -> dict:
    base = {
        "staff_id": str(STAFF_ID),
        "service_start": SERVICE_START.isoformat(),
    }
    base.update(overrides)
    return base


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


def test_admin_reschedule_unauthenticated_401() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
            json=_payload(),
        )
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_admin_reschedule_forbidden_for_non_admin(role: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
        headers=headers,
        json=_payload(),
    )
    assert response.status_code == 403
    mock_booking.admin_reschedule_booking.assert_not_called()
    client.close()


def test_admin_reschedule_cross_tenant_403() -> None:
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
            f"/api/v1/salons/{SALON_B}/bookings/{BOOKING_ID}/reschedule",
            headers={"Authorization": f"Bearer {token}"},
            json=_payload(),
        )
    assert response.status_code == 403
    mock_booking.admin_reschedule_booking.assert_not_called()


def test_admin_reschedule_booking_not_in_salon_404() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_reschedule_booking.side_effect = BookingNotFoundError(
        "booking not found"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
        headers=headers,
        json=_payload(),
    )
    assert response.status_code == 404
    kwargs = mock_booking.admin_reschedule_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    assert kwargs["booking_id"] == BOOKING_ID
    assert kwargs["as_of"] == FIXED_AS_OF
    client.close()


@pytest.mark.parametrize("role", ["owner", "admin"])
@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_admin_reschedule_success_delegates(role: str, status: str) -> None:
    client, mock_booking, headers = _auth_app(role=role)
    mock_booking.admin_reschedule_booking.return_value = RescheduleBookingResult(
        booking_id=BOOKING_ID,
        status=status,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
        headers=headers,
        json=_payload(),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["booking_id"] == str(BOOKING_ID)
    assert body["status"] == status
    kwargs = mock_booking.admin_reschedule_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    assert kwargs["new_staff_id"] == STAFF_ID
    client.close()


def test_admin_reschedule_in_progress_rejected_422() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_reschedule_booking.side_effect = BookingValidationError(
        "booking cannot be rescheduled in its current status"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
        headers=headers,
        json=_payload(),
    )
    assert response.status_code == 422
    client.close()


def test_admin_reschedule_slot_unavailable_409() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_reschedule_booking.side_effect = SlotNotAvailableError(
        "no free gap for requested occupied interval"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
        headers=headers,
        json=_payload(),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "slot_not_available"
    client.close()


def test_admin_reschedule_overlap_409() -> None:
    client, mock_booking, headers = _auth_app()
    mock_booking.admin_reschedule_booking.side_effect = BookingOverlapError(
        "booking overlaps an existing appointment"
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/bookings/{BOOKING_ID}/reschedule",
        headers=headers,
        json=_payload(),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "booking_overlap"
    client.close()
