from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_as_of, get_public_booking_service
from app.main import create_app
from app.services.availability.errors import ServiceNotFoundError
from app.services.booking.errors import (
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)
from app.services.public_booking.types import PublicBookingResult

from tests.api.conftest import FIXED_AS_OF, SALON_ID

CUSTOMER_ID = UUID("33333333-3333-4333-8333-333333333333")
STAFF_ID = UUID("22222222-2222-4222-8222-222222222222")
SERVICE_ID = UUID("44444444-4444-4444-8444-444444444444")
SERVICE_START = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
SERVICE_END = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)


def _public_payload(**overrides: object) -> dict:
    base = {
        "customer_id": str(CUSTOMER_ID),
        "staff_id": str(STAFF_ID),
        "service_id": str(SERVICE_ID),
        "service_start": SERVICE_START.isoformat(),
    }
    base.update(overrides)
    return base


def test_public_booking_delegates_to_service() -> None:
    app = create_app()
    mock_service = MagicMock()
    booking_id = uuid4()
    hold = FIXED_AS_OF + timedelta(seconds=900)
    mock_service.create_public_booking.return_value = PublicBookingResult(
        booking_id=booking_id,
        status="pending",
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
        hold_expires_at=hold,
    )
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["booking_id"] == str(booking_id)
    assert body["status"] == "pending"
    assert body["service_id"] == str(SERVICE_ID)
    assert body["staff_id"] == str(STAFF_ID)
    assert body["service_start"] == SERVICE_START.isoformat().replace("+00:00", "Z")
    assert body["service_end"] == SERVICE_END.isoformat().replace("+00:00", "Z")
    assert "starts_at" not in body
    assert "ends_at" not in body
    assert body["hold_expires_at"] is not None

    mock_service.create_public_booking.assert_called_once()
    kwargs = mock_service.create_public_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["as_of"] == FIXED_AS_OF
    assert kwargs["service_start"] == SERVICE_START
    assert kwargs["customer_notes"] is None


def test_public_booking_tenant_salon_from_path() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.return_value = PublicBookingResult(
        booking_id=uuid4(),
        status="pending",
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
        hold_expires_at=FIXED_AS_OF + timedelta(seconds=900),
    )
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    other_salon = uuid4()
    with TestClient(app) as client:
        client.post(
            f"/api/v1/salons/{other_salon}/bookings/public",
            json=_public_payload(),
        )
    assert mock_service.create_public_booking.call_args.kwargs["salon_id"] == other_salon


def test_public_booking_extra_fields_forbidden(client: TestClient) -> None:
    payload = _public_payload(source="public", status="pending")
    response = client.post(
        f"/api/v1/salons/{SALON_ID}/bookings/public",
        json=payload,
    )
    assert response.status_code == 422


def test_public_booking_invalid_body_422(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/salons/{SALON_ID}/bookings/public",
        json={"customer_id": str(CUSTOMER_ID)},
    )
    assert response.status_code == 422


def test_public_booking_service_not_found_404() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.side_effect = ServiceNotFoundError("service not found")
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_public_booking_slot_not_available_409() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.side_effect = SlotNotAvailableError("taken")
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "slot_not_available"


def test_public_booking_overlap_409() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.side_effect = BookingOverlapError("race")
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "booking_overlap"


def test_public_booking_validation_inactive_service_422() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.side_effect = BookingValidationError(
        "service is not active"
    )
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 422


def test_public_booking_not_found_customer_404() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.side_effect = BookingNotFoundError(
        "customer not found for salon"
    )
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 404


def test_client_cannot_inject_as_of_in_body() -> None:
    app = create_app()
    mock_service = MagicMock()
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    payload = _public_payload()
    payload["as_of"] = "2019-01-01T00:00:00Z"

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=payload,
        )

    assert response.status_code == 422
    mock_service.create_public_booking.assert_not_called()


def test_public_booking_sqlalchemy_error_not_exposed() -> None:
    app = create_app()
    mock_service = MagicMock()
    mock_service.create_public_booking.side_effect = SQLAlchemyError("SELECT * FROM secret")
    app.dependency_overrides[get_public_booking_service] = lambda: mock_service
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as c:
        response = c.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json=_public_payload(),
        )

    assert response.status_code == 500
    assert "SELECT" not in response.text
    assert "secret" not in response.text
