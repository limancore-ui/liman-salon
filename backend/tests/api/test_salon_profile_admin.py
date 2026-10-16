from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_salon_profile_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.salon_profile.service import SalonProfileService, SalonProfileView

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)
PROFILE_URL = f"/api/v1/salons/{SALON_A}/profile"
OTHER_URL = f"/api/v1/salons/{SALON_B}/profile"


def _view(**kwargs: object) -> SalonProfileView:
    defaults: dict[str, object] = {
        "salon_id": SALON_A,
        "name": "Liman",
        "slug": "liman",
    }
    defaults.update(kwargs)
    return SalonProfileView(**defaults)  # type: ignore[arg-type]


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
    mock_profile = MagicMock(spec=SalonProfileService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_salon_profile_service] = lambda: mock_profile
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_profile, headers


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_patch_name_owner_admin(role: str) -> None:
    client, mock_svc, headers = _auth_app(role=role)
    mock_svc.update_name.return_value = _view(name="Новое название")
    response = client.patch(
        PROFILE_URL,
        headers=headers,
        json={"name": "  Новое название  "},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "salon_id": str(SALON_A),
        "name": "Новое название",
        "slug": "liman",
    }
    mock_svc.update_name.assert_called_once_with(
        salon_id=SALON_A,
        name="Новое название",
    )
    client.close()


def test_patch_trims_before_service() -> None:
    """Pydantic validator trims; service receives cleaned name."""
    client, mock_svc, headers = _auth_app()
    mock_svc.update_name.return_value = _view(name="Trimmed")
    response = client.patch(
        PROFILE_URL,
        headers=headers,
        json={"name": "  Trimmed  "},
    )
    assert response.status_code == 200
    assert mock_svc.update_name.call_args.kwargs["name"] == "Trimmed"
    client.close()


def test_patch_empty_name_422() -> None:
    client, mock_svc, headers = _auth_app()
    response = client.patch(
        PROFILE_URL,
        headers=headers,
        json={"name": "   "},
    )
    assert response.status_code == 422
    mock_svc.update_name.assert_not_called()
    client.close()


def test_patch_too_long_422() -> None:
    client, mock_svc, headers = _auth_app()
    response = client.patch(
        PROFILE_URL,
        headers=headers,
        json={"name": "x" * 201},
    )
    assert response.status_code == 422
    mock_svc.update_name.assert_not_called()
    client.close()


def test_patch_unauthenticated_401() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert (
            client.patch(PROFILE_URL, json={"name": "X"}).status_code == 401
        )


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_patch_forbidden_role(role: str) -> None:
    client, mock_svc, headers = _auth_app(role=role)
    response = client.patch(
        PROFILE_URL,
        headers=headers,
        json={"name": "Nope"},
    )
    assert response.status_code == 403
    mock_svc.update_name.assert_not_called()
    client.close()


def test_other_salon_denied_without_membership() -> None:
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
    response = client.patch(
        OTHER_URL,
        headers=headers,
        json={"name": "Hijack"},
    )
    assert response.status_code == 403
    mock_svc.update_name.assert_not_called()
    client.close()
