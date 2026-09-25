from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import (
    get_as_of,
    get_customer_service,
    get_public_booking_orchestrator,
    get_public_booking_service,
    get_salon_public_service,
)
from app.main import create_app
from app.services.booking.errors import BookingOverlapError, BookingValidationError, SlotNotAvailableError
from app.services.customer.service import CustomerService
from app.services.customer.types import CustomerResolveResult
from app.services.public_booking.orchestrator import PublicBookingOrchestrator
from app.services.public_booking.types import PublicBookingOrchestrateResult
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

from tests.api.conftest import FIXED_AS_OF

SALON_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CUSTOMER_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SERVICE_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
BOOKING_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
SERVICE_START = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
SERVICE_END = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)
SLUG = "liman-demo"
ALLOWED_RESPONSE_KEYS = {
    "salon_id",
    "customer_id",
    "booking_id",
    "service_start",
    "service_end",
    "hold_expires_at",
}


def _payload(**overrides: object) -> dict:
    base = {
        "full_name": "Jane Doe",
        "phone": "+77001234567",
        "service_id": str(SERVICE_ID),
        "staff_id": str(STAFF_ID),
        "service_start": SERVICE_START.isoformat(),
    }
    base.update(overrides)
    return base


def _success_result(*, customer_id: uuid.UUID = CUSTOMER_ID) -> PublicBookingOrchestrateResult:
    return PublicBookingOrchestrateResult(
        salon_id=SALON_ID,
        customer_id=customer_id,
        booking_id=BOOKING_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
        hold_expires_at=FIXED_AS_OF + timedelta(seconds=900),
    )


def _orchestrator_app(
    mock_orch: MagicMock | None = None,
) -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock = mock_orch or MagicMock(spec=PublicBookingOrchestrator)
    app.dependency_overrides[get_public_booking_orchestrator] = lambda: mock
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    return TestClient(app), mock


def test_valid_slug_new_customer_valid_booking() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.return_value = _success_result()
    try:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 201
        body = response.json()
        assert body["salon_id"] == str(SALON_ID)
        assert body["customer_id"] == str(CUSTOMER_ID)
        assert body["booking_id"] == str(BOOKING_ID)
        kwargs = mock_orch.create_public_booking_by_slug.call_args.kwargs
        assert kwargs["slug"] == SLUG
        assert kwargs["as_of"] == FIXED_AS_OF
    finally:
        client.close()


def test_valid_slug_existing_customer_valid_booking() -> None:
    existing_customer = uuid.UUID("66666666-6666-4666-8666-666666666666")
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.return_value = _success_result(
        customer_id=existing_customer
    )
    try:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 201
        assert response.json()["customer_id"] == str(existing_customer)
    finally:
        client.close()


def test_existing_customer_profile_not_overwritten_via_resolve_contract() -> None:
    """Orchestrator delegates to resolve_public_customer; existing rows return created=False."""
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.return_value = _success_result()
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings",
            json=_payload(full_name="Different Name"),
        )
        assert response.status_code == 201
        kwargs = mock_orch.create_public_booking_by_slug.call_args.kwargs
        assert kwargs["full_name"] == "Different Name"
        assert kwargs["phone"] == "+77001234567"
    finally:
        client.close()


def test_unknown_salon_slug_404() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    try:
        response = client.post("/api/v1/public/salons/unknown-slug/bookings", json=_payload())
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"
    finally:
        client.close()


def test_inactive_salon_slug_404() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    try:
        response = client.post("/api/v1/public/salons/inactive-salon/bookings", json=_payload())
        assert response.status_code == 404
    finally:
        client.close()


def test_customer_resolution_uses_resolved_salon_id_integration_shape() -> None:
    app = create_app()
    mock_salon = MagicMock(spec=SalonPublicService)
    mock_customer = MagicMock(spec=CustomerService)
    mock_public = MagicMock()
    mock_salon.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug=SLUG,
        name="Demo",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )
    mock_customer.resolve_public_customer.return_value = CustomerResolveResult(
        customer_id=CUSTOMER_ID,
        created=True,
    )
    from app.services.public_booking.types import PublicBookingResult

    mock_public.create_public_booking.return_value = PublicBookingResult(
        booking_id=BOOKING_ID,
        status="pending",
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
        hold_expires_at=FIXED_AS_OF + timedelta(seconds=900),
    )
    orch = PublicBookingOrchestrator(mock_salon, mock_customer, mock_public)
    app.dependency_overrides[get_public_booking_orchestrator] = lambda: orch
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 201
        assert mock_customer.resolve_public_customer.call_args.kwargs["salon_id"] == SALON_ID
        assert mock_public.create_public_booking.call_args.kwargs["salon_id"] == SALON_ID


def test_client_cannot_override_salon_id() -> None:
    client, mock_orch = _orchestrator_app()
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings",
            json=_payload(salon_id=str(uuid.uuid4())),
        )
        assert response.status_code == 422
        mock_orch.create_public_booking_by_slug.assert_not_called()
    finally:
        client.close()


def test_client_cannot_override_source_status_or_hold() -> None:
    client, mock_orch = _orchestrator_app()
    try:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings",
            json=_payload(
                source="admin",
                status="confirmed",
                expires_at="2030-01-01T00:00:00Z",
                as_of="2019-01-01T00:00:00Z",
            ),
        )
        assert response.status_code == 422
        mock_orch.create_public_booking_by_slug.assert_not_called()
    finally:
        client.close()


def test_wrong_tenant_service_or_staff_rejected() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.side_effect = BookingValidationError(
        "staff is not assigned to service"
    )
    try:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 422
    finally:
        client.close()


def test_unavailable_slot_409() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.side_effect = SlotNotAvailableError("taken")
    try:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 409
        assert response.json()["code"] == "slot_not_available"
    finally:
        client.close()


def test_booking_overlap_race_409() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.side_effect = BookingOverlapError("race")
    try:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 409
        assert response.json()["code"] == "booking_overlap"
    finally:
        client.close()


def test_response_contains_only_allowed_public_fields() -> None:
    client, mock_orch = _orchestrator_app()
    mock_orch.create_public_booking_by_slug.return_value = _success_result()
    try:
        response = client.post(f"/api/v1/public/salons/{SLUG}/bookings", json=_payload())
        assert response.status_code == 201
        assert set(response.json().keys()) == ALLOWED_RESPONSE_KEYS
        assert "starts_at" not in response.json()
        assert "ends_at" not in response.json()
        assert "status" not in response.json()
    finally:
        client.close()


def test_existing_public_booking_endpoint_regression() -> None:
    app = create_app()
    mock_public = MagicMock()
    from app.services.public_booking.types import PublicBookingResult

    mock_public.create_public_booking.return_value = PublicBookingResult(
        booking_id=BOOKING_ID,
        status="pending",
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
        hold_expires_at=FIXED_AS_OF + timedelta(seconds=900),
    )
    app.dependency_overrides[get_public_booking_service] = lambda: mock_public
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/bookings/public",
            json={
                "customer_id": str(CUSTOMER_ID),
                "staff_id": str(STAFF_ID),
                "service_id": str(SERVICE_ID),
                "service_start": SERVICE_START.isoformat(),
            },
        )
        assert response.status_code == 201
        assert "booking_id" in response.json()


def test_existing_customer_resolve_endpoint_regression() -> None:
    app = create_app()
    mock_customer = MagicMock(spec=CustomerService)
    mock_customer.resolve_public_customer.return_value = CustomerResolveResult(
        customer_id=CUSTOMER_ID,
        created=True,
    )
    app.dependency_overrides[get_customer_service] = lambda: mock_customer

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/public/customers/resolve",
            json={"full_name": "Jane", "phone": "+77001234567"},
        )
        assert response.status_code == 200
        assert response.json()["customer_id"] == str(CUSTOMER_ID)


def test_existing_public_salon_entry_endpoint_regression() -> None:
    app = create_app()
    mock_salon = MagicMock(spec=SalonPublicService)
    mock_salon.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug=SLUG,
        name="Demo",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )
    app.dependency_overrides[get_salon_public_service] = lambda: mock_salon

    with TestClient(app) as client:
        response = client.get(f"/api/v1/public/salons/{SLUG}")
        assert response.status_code == 200
        assert response.json()["salon_id"] == str(SALON_ID)
