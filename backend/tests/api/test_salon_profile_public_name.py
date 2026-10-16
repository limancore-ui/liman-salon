from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_salon_public_service
from app.main import create_app
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

SALON_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def test_public_salon_entry_reflects_updated_name() -> None:
    """After profile rename, public entry exposes salons.name (no appearance storage)."""
    app = create_app()
    mock_svc = MagicMock(spec=SalonPublicService)
    mock_svc.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug="malina-beauty-test",
        name="Новое название салона",
        currency_code="KGS",
        timezone="Asia/Bishkek",
        logo_media_id=None,
        background_media_id=None,
        appearance=None,
    )
    app.dependency_overrides[get_salon_public_service] = lambda: mock_svc
    with TestClient(app) as client:
        response = client.get("/api/v1/public/salons/malina-beauty-test")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Новое название салона"
        assert body["slug"] == "malina-beauty-test"
        assert "settings" not in body
