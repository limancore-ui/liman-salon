from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_public_catalog_service
from app.main import create_app
from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.types import (
    ServiceAvailabilityResult,
    ServiceAvailabilitySlot,
    StaffServiceAvailability,
)
from app.services.public_catalog.service import PublicCatalogService
from app.services.public_catalog.types import (
    PublicCatalogServiceItem,
    PublicCatalogServicesResult,
    PublicCatalogStaffMember,
    PublicCatalogStaffResult,
)
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.service_catalog.errors import ServiceCatalogNotFoundError

from tests.api.conftest import FIXED_AS_OF, SALON_ID

SERVICE_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
STAFF_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
SLUG = "liman-demo"


def _catalog_app() -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock = MagicMock(spec=PublicCatalogService)
    app.dependency_overrides[get_public_catalog_service] = lambda: mock
    return TestClient(app), mock


def test_public_services_active_returned() -> None:
    client, mock = _catalog_app()
    mock.list_active_services_by_slug.return_value = PublicCatalogServicesResult(
        salon_id=SALON_ID,
        services=(
            PublicCatalogServiceItem(
                id=SERVICE_ID,
                name="Haircut",
                description="Basic cut",
                duration_minutes=45,
                buffer_before_minutes=0,
                buffer_after_minutes=5,
                price_cents=500000,
                currency_code="KZT",
            ),
        ),
    )
    try:
        response = client.get(f"/api/v1/public/salons/{SLUG}/services")
        assert response.status_code == 200
        body = response.json()
        assert body["salon_id"] == str(SALON_ID)
        assert len(body["services"]) == 1
        assert body["services"][0]["name"] == "Haircut"
        assert body["services"][0]["currency_code"] == "KZT"
        mock.list_active_services_by_slug.assert_called_once_with(SLUG)
    finally:
        client.close()


def test_public_services_unknown_slug_404() -> None:
    client, mock = _catalog_app()
    mock.list_active_services_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    response = client.get("/api/v1/public/salons/missing/services")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_public_services_inactive_salon_404() -> None:
    client, mock = _catalog_app()
    mock.list_active_services_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    response = client.get("/api/v1/public/salons/inactive-salon/services")
    assert response.status_code == 404


def test_public_services_response_field_allowlist() -> None:
    client, mock = _catalog_app()
    mock.list_active_services_by_slug.return_value = PublicCatalogServicesResult(
        salon_id=SALON_ID,
        services=(
            PublicCatalogServiceItem(
                id=SERVICE_ID,
                name="X",
                description=None,
                duration_minutes=30,
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                price_cents=0,
                currency_code="KZT",
            ),
        ),
    )
    try:
        response = client.get(f"/api/v1/public/salons/{SLUG}/services")
        body = response.json()
        assert set(body.keys()) == {"salon_id", "services"}
        assert set(body["services"][0].keys()) == {
            "id",
            "name",
            "description",
            "duration_minutes",
            "buffer_before_minutes",
            "buffer_after_minutes",
            "price_cents",
            "currency_code",
        }
    finally:
        client.close()


def test_public_services_no_auth_required() -> None:
    client, mock = _catalog_app()
    mock.list_active_services_by_slug.return_value = PublicCatalogServicesResult(
        salon_id=SALON_ID,
        services=(),
    )
    response = client.get(f"/api/v1/public/salons/{SLUG}/services")
    assert response.status_code != 401


def test_public_service_staff_active_assigned_returned() -> None:
    client, mock = _catalog_app()
    mock.list_bookable_staff_for_service_by_slug.return_value = PublicCatalogStaffResult(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        staff=(PublicCatalogStaffMember(id=STAFF_ID, display_name="Sam"),),
    )
    try:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/services/{SERVICE_ID}/staff"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["staff"][0]["display_name"] == "Sam"
        mock.list_bookable_staff_for_service_by_slug.assert_called_once_with(
            slug=SLUG,
            service_id=SERVICE_ID,
        )
    finally:
        client.close()


def test_public_service_staff_missing_service_404() -> None:
    client, mock = _catalog_app()
    mock.list_bookable_staff_for_service_by_slug.side_effect = (
        ServiceCatalogNotFoundError("service not found")
    )
    response = client.get(
        f"/api/v1/public/salons/{SLUG}/services/{SERVICE_ID}/staff"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_public_service_staff_response_field_allowlist() -> None:
    client, mock = _catalog_app()
    mock.list_bookable_staff_for_service_by_slug.return_value = PublicCatalogStaffResult(
        salon_id=SALON_ID,
        service_id=SERVICE_ID,
        staff=(PublicCatalogStaffMember(id=STAFF_ID, display_name="Sam"),),
    )
    try:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/services/{SERVICE_ID}/staff"
        )
        body = response.json()
        assert set(body.keys()) == {"salon_id", "service_id", "staff"}
        assert set(body["staff"][0].keys()) == {"id", "display_name"}
    finally:
        client.close()


def test_public_slug_availability_delegates_with_resolved_salon() -> None:
    app = create_app()
    mock = MagicMock(spec=PublicCatalogService)
    slot_start = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
    slot_end = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)
    mock.get_service_availability_by_slug.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(
            StaffServiceAvailability(
                staff_id=STAFF_ID,
                slots=(
                    ServiceAvailabilitySlot(
                        service_start=slot_start,
                        service_end=slot_end,
                    ),
                ),
            ),
        ),
    )
    app.dependency_overrides[get_public_catalog_service] = lambda: mock
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
                "staff_id": str(STAFF_ID),
            },
        )

    assert response.status_code == 200
    mock.get_service_availability_by_slug.assert_called_once_with(
        slug=SLUG,
        service_id=SERVICE_ID,
        start_date=date(2026, 9, 25),
        end_date=date(2026, 9, 25),
        staff_id=STAFF_ID,
        as_of=FIXED_AS_OF,
    )


def test_public_slug_availability_optional_staff_id_omitted() -> None:
    app = create_app()
    mock = MagicMock(spec=PublicCatalogService)
    mock.get_service_availability_by_slug.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(),
    )
    app.dependency_overrides[get_public_catalog_service] = lambda: mock
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF

    with TestClient(app) as client:
        client.get(
            f"/api/v1/public/salons/{SLUG}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
            },
        )

    assert mock.get_service_availability_by_slug.call_args.kwargs["staff_id"] is None


def test_public_slug_availability_unknown_salon_404() -> None:
    client, mock = _catalog_app()
    mock.get_service_availability_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    app = client.app
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    response = client.get(
        f"/api/v1/public/salons/unknown/availability/service",
        params={
            "service_id": str(SERVICE_ID),
            "start_date": "2026-09-25",
            "end_date": "2026-09-25",
        },
    )
    assert response.status_code == 404


def test_public_slug_availability_wrong_tenant_empty_staff() -> None:
    client, mock = _catalog_app()
    mock.get_service_availability_by_slug.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(),
    )
    app = client.app
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    response = client.get(
        f"/api/v1/public/salons/{SLUG}/availability/service",
        params={
            "service_id": str(SERVICE_ID),
            "start_date": "2026-09-25",
            "end_date": "2026-09-25",
            "staff_id": str(STAFF_ID),
        },
    )
    assert response.status_code == 200
    assert response.json()["staff"] == []


def test_public_slug_availability_service_not_found_404() -> None:
    client, mock = _catalog_app()
    mock.get_service_availability_by_slug.side_effect = ServiceNotFoundError(
        "service not found"
    )
    app = client.app
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    response = client.get(
        f"/api/v1/public/salons/{SLUG}/availability/service",
        params={
            "service_id": str(SERVICE_ID),
            "start_date": "2026-09-25",
            "end_date": "2026-09-25",
        },
    )
    assert response.status_code == 404


def test_public_slug_availability_client_cannot_set_as_of() -> None:
    app = create_app()
    mock = MagicMock(spec=PublicCatalogService)
    mock.get_service_availability_by_slug.return_value = ServiceAvailabilityResult(
        service_id=SERVICE_ID,
        staff=(),
    )
    app.dependency_overrides[get_public_catalog_service] = lambda: mock
    fake_as_of = datetime(2020, 1, 1, tzinfo=timezone.utc)
    app.dependency_overrides[get_as_of] = lambda: fake_as_of

    with TestClient(app) as client:
        client.get(
            f"/api/v1/public/salons/{SLUG}/availability/service",
            params={
                "service_id": str(SERVICE_ID),
                "start_date": "2026-09-25",
                "end_date": "2026-09-25",
                "as_of": "2020-01-01T00:00:00Z",
            },
        )

    assert mock.get_service_availability_by_slug.call_args.kwargs["as_of"] == fake_as_of


def test_public_catalog_does_not_duplicate_availability_engine() -> None:
    """Route delegates to PublicCatalogService.get_service_availability_by_slug only."""
    import inspect

    from app.api.v1 import salons_public

    source = inspect.getsource(salons_public.get_public_service_availability_by_slug)
    assert "get_free_gaps" not in source
    assert "net_service_slots_from_free_gaps" not in source
    assert "get_service_availability_by_slug" in source


def test_existing_public_salon_entry_unchanged_openapi() -> None:
    client = TestClient(create_app())
    try:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/public/salons/{slug}" in paths
        get_op = paths["/api/v1/public/salons/{slug}"]["get"]
        assert "PublicSalonEntryResponse" in get_op["responses"]["200"]["content"][
            "application/json"
        ]["schema"]["$ref"]
    finally:
        client.close()


def test_existing_public_booking_flow_unchanged_openapi() -> None:
    client = TestClient(create_app())
    try:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/public/salons/{slug}/bookings" in paths
        assert "/api/v1/salons/{salon_id}/bookings/public" in paths
        assert "/api/v1/salons/{salon_id}/public/customers/resolve" in paths
        assert "/api/v1/salons/{salon_id}/availability/service" in paths
    finally:
        client.close()


def test_new_public_catalog_routes_registered() -> None:
    client = TestClient(create_app())
    try:
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/v1/public/salons/{slug}/services" in paths
        assert "/api/v1/public/salons/{slug}/services/{service_id}/staff" in paths
        assert "/api/v1/public/salons/{slug}/availability/service" in paths
    finally:
        client.close()
