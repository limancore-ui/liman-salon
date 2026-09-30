from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_as_of, get_booking_service, get_salon_public_service
from app.main import create_app
from app.services.booking.errors import BookingNotFoundError, BookingValidationError
from app.services.booking.types import CancelBookingResult
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

from tests.api.conftest import FIXED_AS_OF

SALON_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOOKING_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
SLUG = "liman-demo"
TOKEN = "mock-cancel-token"
CANCELLED_AT = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
ALLOWED_RESPONSE_KEYS = {"booking_id", "status", "cancelled_at"}


def _cancel_payload(**overrides: object) -> dict:
    base = {"token": TOKEN}
    base.update(overrides)
    return base


def _cancel_app() -> tuple[TestClient, MagicMock, MagicMock]:
    app = create_app()
    mock_booking = MagicMock()
    mock_salon = MagicMock(spec=SalonPublicService)
    mock_salon.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug=SLUG,
        name="Demo",
        currency_code="KZT",
        timezone="UTC",
        logo_media_id=None,
    )
    app.dependency_overrides[get_booking_service] = lambda: mock_booking
    app.dependency_overrides[get_salon_public_service] = lambda: mock_salon
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    return TestClient(app), mock_booking, mock_salon


def test_public_cancel_delegates_to_booking_service() -> None:
    client, mock_booking, mock_salon = _cancel_app()
    mock_booking.cancel_booking.return_value = CancelBookingResult(
        booking_id=BOOKING_ID,
        status="cancelled",
        cancelled_at=CANCELLED_AT,
    )
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json=_cancel_payload(reason="no longer needed"),
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == ALLOWED_RESPONSE_KEYS
        assert body["booking_id"] == str(BOOKING_ID)
        assert body["status"] == "cancelled"
        assert body["cancelled_at"] is not None

        mock_salon.resolve_public_salon_by_slug.assert_called_once_with(SLUG)
        kwargs = mock_booking.cancel_booking.call_args.kwargs
        assert kwargs["salon_id"] == SALON_ID
        assert kwargs["booking_id"] == BOOKING_ID
        assert kwargs["token"] == TOKEN
        assert kwargs["reason"] == "no longer needed"
        assert kwargs["as_of"] == FIXED_AS_OF
    finally:
        client.close()


def test_public_cancel_unknown_slug_404() -> None:
    client, mock_booking, mock_salon = _cancel_app()
    mock_salon.resolve_public_salon_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    try:
        response = client.post(
            f"/api/v1/public/salons/unknown/bookings/{BOOKING_ID}/cancel",
            json=_cancel_payload(),
        )
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
        mock_booking.cancel_booking.assert_not_called()
    finally:
        client.close()


def test_public_cancel_wrong_token_404_not_found() -> None:
    client, mock_booking, _mock_salon = _cancel_app()
    mock_booking.cancel_booking.side_effect = BookingNotFoundError("booking not found")
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json=_cancel_payload(token="bad"),
        )
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
        assert "token" not in response.text.lower()
    finally:
        client.close()


def test_public_cancel_terminal_status_422() -> None:
    client, mock_booking, _mock_salon = _cancel_app()
    mock_booking.cancel_booking.side_effect = BookingValidationError(
        "booking cannot be cancelled in its current status"
    )
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json=_cancel_payload(),
        )
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
    finally:
        client.close()


def test_public_cancel_extra_fields_forbidden() -> None:
    client, mock_booking, _mock_salon = _cancel_app()
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json={**_cancel_payload(), "salon_id": str(SALON_ID)},
        )
        assert response.status_code == 422
        mock_booking.cancel_booking.assert_not_called()
    finally:
        client.close()


def test_public_cancel_missing_token_422() -> None:
    client, mock_booking, _mock_salon = _cancel_app()
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json={},
        )
        assert response.status_code == 422
        mock_booking.cancel_booking.assert_not_called()
    finally:
        client.close()


def test_public_cancel_no_jwt_required() -> None:
    """Public cancel must not require Authorization header."""
    client, mock_booking, _mock_salon = _cancel_app()
    mock_booking.cancel_booking.return_value = CancelBookingResult(
        booking_id=BOOKING_ID,
        status="cancelled",
        cancelled_at=CANCELLED_AT,
    )
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json=_cancel_payload(),
        )
        assert response.status_code == 200
    finally:
        client.close()


def test_public_cancel_sqlalchemy_error_not_exposed() -> None:
    client, mock_booking, _mock_salon = _cancel_app()
    mock_booking.cancel_booking.side_effect = SQLAlchemyError("SELECT * FROM secret")
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings/{BOOKING_ID}/cancel",
            json=_cancel_payload(),
        )
        assert response.status_code == 500
        assert "SELECT" not in response.text
        assert "secret" not in response.text
    finally:
        client.close()
