from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_salon_appearance_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.salon_appearance.errors import (
    SalonAppearanceError,
    SalonAppearanceNotFoundError,
)
from app.services.salon_appearance.service import (
    SalonAppearanceService,
    SalonAppearanceView,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)
APPEARANCE_URL = f"/api/v1/salons/{SALON_A}/appearance"
OTHER_URL = f"/api/v1/salons/{SALON_B}/appearance"


def _view(**kwargs: object) -> SalonAppearanceView:
    defaults: dict[str, object] = {
        "salon_id": SALON_A,
        "salon_name": "Liman",
        "primary_color": None,
        "accent_soft_color": None,
        "background_color": None,
        "logo_media_id": None,
        "background_media_id": None,
    }
    defaults.update(kwargs)
    return SalonAppearanceView(**defaults)  # type: ignore[arg-type]


def _auth_app(
    *, role: str = "owner", salon_id: uuid.UUID = SALON_A
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
    mock_appearance = MagicMock(spec=SalonAppearanceService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_salon_appearance_service] = lambda: mock_appearance
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_appearance, headers


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_get_appearance_owner_admin(role: str) -> None:
    client, mock_svc, headers = _auth_app(role=role)
    mock_svc.get_appearance.return_value = _view(
        primary_color="#2f6b4f",
        accent_soft_color="#e8f2ec",
        background_color="#f4f7f5",
    )
    response = client.get(APPEARANCE_URL, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["primary_color"] == "#2f6b4f"
    assert body["salon_name"] == "Liman"
    mock_svc.get_appearance.assert_called_once_with(salon_id=SALON_A)
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_get_appearance_forbidden(role: str) -> None:
    client, mock_svc, headers = _auth_app(role=role)
    response = client.get(APPEARANCE_URL, headers=headers)
    assert response.status_code == 403
    mock_svc.get_appearance.assert_not_called()
    client.close()


def test_get_appearance_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(APPEARANCE_URL).status_code == 401


def test_other_salon_path_denied_without_membership() -> None:
    """Requesting another salon_id without membership returns 403 (tenant isolation)."""
    client, mock_svc, headers = _auth_app(role="owner", salon_id=SALON_A)
    app = client.app
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B,
        name="Other",
        slug="other",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    response = client.get(OTHER_URL, headers=headers)
    assert response.status_code == 403
    mock_svc.get_appearance.assert_not_called()
    client.close()


def test_patch_colors() -> None:
    client, mock_svc, headers = _auth_app(role="owner")
    mock_svc.patch_appearance.return_value = _view(
        primary_color="#1e4d7b",
        accent_soft_color="#e3eef8",
        background_color="#f5f7fa",
    )
    response = client.patch(
        APPEARANCE_URL,
        headers=headers,
        json={
            "colors": {
                "primary_color": "#1e4d7b",
                "accent_soft_color": "#e3eef8",
                "background_color": "#f5f7fa",
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["primary_color"] == "#1e4d7b"
    mock_svc.patch_appearance.assert_called_once()
    client.close()


def test_patch_invalid_color_422() -> None:
    client, mock_svc, headers = _auth_app(role="owner")
    response = client.patch(
        APPEARANCE_URL,
        headers=headers,
        json={"colors": {"primary_color": "red"}},
    )
    assert response.status_code == 422
    mock_svc.patch_appearance.assert_not_called()
    client.close()


def test_patch_rejects_external_url_as_color() -> None:
    client, mock_svc, headers = _auth_app(role="owner")
    response = client.patch(
        APPEARANCE_URL,
        headers=headers,
        json={"colors": {"background_color": "url(https://evil.example/x)"}},
    )
    assert response.status_code == 422
    mock_svc.patch_appearance.assert_not_called()
    client.close()


def test_get_not_found() -> None:
    client, mock_svc, headers = _auth_app()
    mock_svc.get_appearance.side_effect = SalonAppearanceNotFoundError("salon not found")
    response = client.get(APPEARANCE_URL, headers=headers)
    assert response.status_code == 404
    client.close()


def test_patch_service_validation_error() -> None:
    client, mock_svc, headers = _auth_app()
    mock_svc.patch_appearance.side_effect = SalonAppearanceError("invalid salon appearance")
    response = client.patch(
        APPEARANCE_URL,
        headers=headers,
        json={"colors": {"primary_color": "#abcdef"}},
    )
    assert response.status_code == 422
    client.close()
