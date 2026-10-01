from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_salon_settings_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.salon_settings.errors import SalonSettingsError, SalonSettingsNotFoundError
from app.services.salon_settings.service import (
    SalonSettingsService,
    SalonSettingsView,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)
SETTINGS_URL = f"/api/v1/salons/{SALON_A}/settings"


def _view(**kwargs: object) -> SalonSettingsView:
    defaults = {
        "stored": {},
        "v": 1,
        "public_hold_seconds": None,
    }
    defaults.update(kwargs)
    return SalonSettingsView(**defaults)


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
    mock_settings = MagicMock(spec=SalonSettingsService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_salon_settings_service] = lambda: mock_settings
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_settings, headers


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_get_settings_owner_admin(role: str) -> None:
    client, mock_settings, headers = _auth_app(role=role)
    mock_settings.get_settings.return_value = _view(
        public_hold_seconds=1200,
        stored={"v": 1, "booking": {"public_hold_seconds": 1200}},
    )
    response = client.get(SETTINGS_URL, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body == {"v": 1, "booking": {"public_hold_seconds": 1200}}
    mock_settings.get_settings.assert_called_once_with(salon_id=SALON_A)
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_get_settings_read_forbidden(role: str) -> None:
    client, mock_settings, headers = _auth_app(role=role)
    response = client.get(SETTINGS_URL, headers=headers)
    assert response.status_code == 403
    mock_settings.get_settings.assert_not_called()
    client.close()


def test_get_settings_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(SETTINGS_URL).status_code == 401


def test_get_settings_no_membership_403() -> None:
    client, mock_settings, headers = _auth_app(role="owner")
    app = client.app
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="o@e.com",
        full_name="O",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_A,
        name="S",
        slug="s",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    response = client.get(SETTINGS_URL, headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "salon_access_denied"
    mock_settings.get_settings.assert_not_called()
    client.close()


def test_get_settings_salon_not_found_404() -> None:
    client, mock_settings, headers = _auth_app()
    mock_settings.get_settings.side_effect = SalonSettingsNotFoundError("salon not found")
    response = client.get(SETTINGS_URL, headers=headers)
    assert response.status_code == 404
    client.close()


def test_patch_set_hold_seconds() -> None:
    client, mock_settings, headers = _auth_app(role="owner")
    mock_settings.patch_settings.return_value = _view(
        public_hold_seconds=1800,
    )
    response = client.patch(
        SETTINGS_URL,
        headers=headers,
        json={"booking": {"public_hold_seconds": 1800}},
    )
    assert response.status_code == 200
    assert response.json()["booking"]["public_hold_seconds"] == 1800
    patch_arg = mock_settings.patch_settings.call_args.kwargs["patch"]
    assert patch_arg.booking_set is True
    assert patch_arg.booking is not None
    assert patch_arg.booking.public_hold_seconds == 1800
    client.close()


def test_patch_clear_booking_null() -> None:
    client, mock_settings, headers = _auth_app(role="admin")
    mock_settings.patch_settings.return_value = _view()
    response = client.patch(SETTINGS_URL, headers=headers, json={"booking": None})
    assert response.status_code == 200
    patch_arg = mock_settings.patch_settings.call_args.kwargs["patch"]
    assert patch_arg.booking_set is True
    assert patch_arg.booking is None
    client.close()


def test_patch_clear_public_hold_null_rejected_422() -> None:
    client, mock_settings, headers = _auth_app(role="owner")
    response = client.patch(
        SETTINGS_URL,
        headers=headers,
        json={"booking": {"public_hold_seconds": None}},
    )
    assert response.status_code == 422
    mock_settings.patch_settings.assert_not_called()
    client.close()


def test_get_settings_platform_default_body() -> None:
    client, mock_settings, headers = _auth_app(role="owner")
    mock_settings.get_settings.return_value = _view()
    response = client.get(SETTINGS_URL, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"v": 1}
    client.close()


def test_patch_staff_forbidden_403() -> None:
    client, mock_settings, headers = _auth_app(role="staff")
    response = client.patch(
        SETTINGS_URL,
        headers=headers,
        json={"booking": {"public_hold_seconds": 900}},
    )
    assert response.status_code == 403
    mock_settings.patch_settings.assert_not_called()
    client.close()


def test_patch_invalid_hold_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.patch(
        SETTINGS_URL,
        headers=headers,
        json={"booking": {"public_hold_seconds": 30}},
    )
    assert response.status_code == 422
    client.close()


def test_patch_service_validation_422() -> None:
    client, mock_settings, headers = _auth_app(role="owner")
    mock_settings.patch_settings.side_effect = SalonSettingsError("invalid salon settings")
    response = client.patch(
        SETTINGS_URL,
        headers=headers,
        json={"booking": {"public_hold_seconds": 1200}},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()


def test_patch_tenant_scoped_salon_id() -> None:
    client, mock_settings, headers = _auth_app(role="owner", salon_id=SALON_A)
    mock_settings.patch_settings.return_value = _view()
    client.patch(
        SETTINGS_URL,
        headers=headers,
        json={"booking": {"public_hold_seconds": 600}},
    )
    assert mock_settings.patch_settings.call_args.kwargs["salon_id"] == SALON_A
    client.close()


def test_cannot_access_salon_b_without_membership() -> None:
    client, mock_settings, headers = _auth_app(role="owner", salon_id=SALON_A)
    app = client.app
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="o@e.com",
        full_name="O",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B,
        name="B",
        slug="b",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    response = client.get(
        f"/api/v1/salons/{SALON_B}/settings",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    mock_settings.get_settings.assert_not_called()
    client.close()
