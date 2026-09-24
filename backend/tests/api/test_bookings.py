from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_as_of, get_booking_service
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

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            json=_booking_payload(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["booking_id"] == str(booking_id)
    assert body["status"] == "confirmed"

    mock_service.create_booking.assert_called_once()
    kwargs = mock_service.create_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["as_of"] == FIXED_AS_OF
    assert kwargs["customer_notes"] is None


def test_booking_tenant_salon_from_path() -> None:
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

    other_salon = uuid4()
    with TestClient(app) as client:
        client.post(
            f"/api/v1/salons/{other_salon}/bookings",
            json=_booking_payload(),
        )
    assert mock_service.create_booking.call_args.kwargs["salon_id"] == other_salon


def test_booking_validation_error_422() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = BookingValidationError("bad status combo")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
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

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
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

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
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

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            json=_booking_payload(),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "booking_overlap"


def test_invalid_request_body_422(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/salons/{SALON_ID}/bookings",
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

    payload = _booking_payload()
    payload["as_of"] = "2019-01-01T00:00:00Z"

    with TestClient(app) as client:
        client.post(f"/api/v1/salons/{SALON_ID}/bookings", json=payload)

    assert mock_service.create_booking.call_args.kwargs["as_of"] == injected


def test_sqlalchemy_error_not_exposed(client: TestClient) -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = SQLAlchemyError("SELECT * FROM secret")
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as c:
        response = c.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            json=_booking_payload(),
        )

    assert response.status_code == 500
    assert "SELECT" not in response.text
    assert "secret" not in response.text


def test_public_pending_requires_expires_at_via_service() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_booking.side_effect = BookingValidationError(
        "public pending booking requires expires_at"
    )
    app.dependency_overrides[get_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            json=_booking_payload(source="public", status="pending"),
        )

    assert response.status_code == 422


def test_public_pending_success_passes_expires_at() -> None:
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

    expires = (FIXED_AS_OF + timedelta(hours=1)).isoformat()
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings",
            json=_booking_payload(
                source="public",
                status="pending",
                expires_at=expires,
            ),
        )

    assert response.status_code == 201
    assert mock_service.create_booking.call_args.kwargs["expires_at"] is not None
