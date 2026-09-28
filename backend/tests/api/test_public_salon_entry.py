from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_salon_public_service
from app.main import create_app
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

SALON_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _public_app() -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock_svc = MagicMock(spec=SalonPublicService)
    app.dependency_overrides[get_salon_public_service] = lambda: mock_svc
    return TestClient(app), mock_svc


def test_get_public_salon_no_auth_required() -> None:
    client, mock_svc = _public_app()
    mock_svc.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug="liman-demo",
        name="Liman Demo",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )
    try:
        response = client.get("/api/v1/public/salons/liman-demo")
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "salon_id": str(SALON_ID),
            "slug": "liman-demo",
            "name": "Liman Demo",
            "currency_code": "KZT",
            "timezone": "Asia/Almaty",
            "logo_media_id": None,
        }
        assert set(body.keys()) == {
            "salon_id",
            "slug",
            "name",
            "currency_code",
            "timezone",
            "logo_media_id",
        }
        mock_svc.resolve_public_salon_by_slug.assert_called_once_with("liman-demo")
    finally:
        client.close()


def test_get_public_salon_not_found_404() -> None:
    client, mock_svc = _public_app()
    mock_svc.resolve_public_salon_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    response = client.get("/api/v1/public/salons/unknown")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_public_booking_route_unchanged_smoke() -> None:
    """Regression: public booking and new public salon paths stay registered."""
    client = TestClient(create_app())
    try:
        openapi = client.get("/openapi.json").json()
        paths = openapi["paths"]
        assert "/api/v1/salons/{salon_id}/bookings/public" in paths
        assert "/api/v1/public/salons/{slug}" in paths
    finally:
        client.close()
