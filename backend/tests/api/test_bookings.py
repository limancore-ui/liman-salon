from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

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
from app.services.booking.types import CreateBookingResult

from tests.api.conftest import FIXED_AS_OF, SALON_ID

CUSTOMER_ID = UUID("33333333-3333-4333-8333-333333333333")
STAFF_ID = UUID("22222222-2222-4222-8222-222222222222")
SERVICE_ID = UUID("44444444-4444-4444-8444-444444444444")
USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
AUTH_NOW = datetime.now(timezone.utc)


def _auth_headers_for_app(app, *, salon_id: UUID = SALON_ID) -> dict[str, str]:
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
        role="owner",
        is_active=True,
    )
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=AUTH_NOW)
    return {"Authorization": f"Bearer {token}"}


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


def test_create_booking_delegates_to_service() -> None:
    app = create_app()
    mock_service = MagicMock()
    booking_id = uuid4()
    starts = datetime(2026, 9, 25, 9, 45, tzinfo=timezone.utc)
    ends = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)
    mock_service.create_booking.return_value = CreateBookingResult(
        booking_id=booking_id,
        starts_at=starts,
        ends_at=ends,
        status="confirmed",
    )
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["booking_id"] == str(booking_id)
    assert body["status"] == "confirmed"

    mock_service.create_booking.assert_called_once()
    kwargs = mock_service.create_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["source"] == "admin"
    assert kwargs["created_by_user_id"] == USER_ID
    assert kwargs["as_of"] == FIXED_AS_OF
    assert kwargs["customer_notes"] is None


def test_booking_validation_error_422() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = BookingValidationError("bad status combo")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(status="pending"),
        )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_booking_not_found_404() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = BookingNotFoundError("staff not found for salon")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(),
        )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_slot_not_available_409() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = SlotNotAvailableError("no gap")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "slot_not_available"


def test_booking_overlap_409() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = BookingOverlapError("overlap")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "booking_overlap"


def test_invalid_request_body_422() -> None:
    app = create_app()
    app.dependency_overrides[get_booking_service] = lambda: MagicMock()
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json={"customer_id": str(CUSTOMER_ID)},
        )
    assert response.status_code == 422


def test_client_cannot_override_as_of_in_body() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.return_value = CreateBookingResult(
        booking_id=uuid4(),
        starts_at=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
        status="confirmed",
    )
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    injected = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    app.dependency_overrides[get_as_of] = lambda: injected
    headers = _auth_headers_for_app(app)

    payload = _booking_payload()
    payload["as_of"] = "2019-01-01T00:00:00Z"

    with TestClient(app) as client:
        client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=payload,
        )

    assert mock_service.create_booking.call_args.kwargs["as_of"] == injected


def test_sqlalchemy_error_not_exposed() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = SQLAlchemyError("SELECT * FROM secret")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as c:
        response = c.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(),
        )

    assert response.status_code == 500
    assert "SELECT" not in response.text
    assert "secret" not in response.text


def test_admin_create_forces_source_admin() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.return_value = CreateBookingResult(
        booking_id=uuid4(),
        starts_at=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
        status="confirmed",
    )
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    with TestClient(app) as client:
        client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(source="public"),
        )

    assert mock_service.create_booking.call_args.kwargs["source"] == "admin"


def test_admin_pending_success_passes_expires_at() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.return_value = CreateBookingResult(
        booking_id=uuid4(),
        starts_at=datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        ends_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
        status="pending",
    )
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    headers = _auth_headers_for_app(app)

    expires = (FIXED_AS_OF + timedelta(hours=1)).isoformat()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            headers=headers,
            json=_booking_payload(
                status="pending",
                expires_at=expires,
            ),
        )

    assert response.status_code == 201
    kwargs = mock_service.create_booking.call_args.kwargs
    assert kwargs["source"] == "admin"
    assert kwargs["expires_at"] is not None
