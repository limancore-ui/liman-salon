from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.auth.deps import get_auth_repository
from app.auth.errors import ForbiddenRoleError
from app.auth.principals import SalonContext
from app.auth.rbac import ensure_role_allowed
from app.core.config import get_settings
from app.core.security import ACCESS_TOKEN_TYPE, create_access_token, hash_password
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SALON_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
OTHER_SALON_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _user(*, active: bool = True, password: str = "secret") -> SimpleNamespace:
    return SimpleNamespace(
        id=USER_ID,
        email="Owner@Example.com",
        full_name="Owner User",
        is_active=active,
        password_hash=hash_password(password),
    )


def _salon(*, active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=SALON_ID,
        name="Liman Demo",
        slug="liman-demo",
        is_active=active,
        timezone="Asia/Almaty",
        currency_code="KZT",
    )


def _membership(*, role: str = "owner", active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        salon_id=SALON_ID,
        user_id=USER_ID,
        role=role,
        is_active=active,
    )


@pytest.fixture
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def auth_client(now_utc: datetime) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_clock] = lambda: (lambda: now_utc)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _token_for(user_id: uuid.UUID = USER_ID, *, now: datetime | None = None) -> str:
    token, _ = create_access_token(user_id=user_id, now=now or datetime.now(timezone.utc))
    return token


def test_login_returns_bearer_token(auth_client: TestClient) -> None:
    app = create_app()
    mock_repo = MagicMock()
    mock_repo.get_user_by_email.return_value = _user()
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    now = datetime.now(timezone.utc)
    app.dependency_overrides[get_clock] = lambda: (lambda: now)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "secret"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == get_settings().access_token_expire_seconds
    assert "access_token" in data
    assert "password_hash" not in response.text


def test_login_wrong_password_generic_401() -> None:
    app = create_app()
    mock_repo = MagicMock()
    mock_repo.get_user_by_email.return_value = _user()
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "wrong"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_login_unknown_email_same_401() -> None:
    app = create_app()
    mock_repo = MagicMock()
    mock_repo.get_user_by_email.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "missing@example.com", "password": "secret"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_inactive_user_cannot_login() -> None:
    app = create_app()
    mock_repo = MagicMock()
    mock_repo.get_user_by_email.return_value = _user(active=False)
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "secret"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_token_expiration_enforced() -> None:
    app = create_app()
    settings = get_settings()
    expired = datetime.now(timezone.utc) - timedelta(hours=1)
    payload = {
        "sub": str(USER_ID),
        "typ": ACCESS_TOKEN_TYPE,
        "iat": int(expired.timestamp()),
        "exp": int((expired + timedelta(minutes=5)).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_wrong_token_type_401() -> None:
    app = create_app()
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(USER_ID),
            "typ": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    mock_repo = MagicMock()
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401


def test_malformed_token_401(auth_client: TestClient) -> None:
    response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-valid-jwt"},
    )
    assert response.status_code == 401


def test_me_resolves_current_user() -> None:
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["user_id"] == str(USER_ID)
    assert response.json()["email"].lower() == "owner@example.com"


def test_inactive_user_rejected_with_valid_token_structure() -> None:
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 401


def test_salon_context_active_membership() -> None:
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    mock_repo.get_active_salon.return_value = _salon()
    mock_repo.get_active_membership.return_value = _membership(role="admin")
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/auth/salons/{SALON_ID}/context",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin"
    assert body["salon_name"] == "Liman Demo"
    assert body["salon_slug"] == "liman-demo"
    assert body["timezone"] == "Asia/Almaty"
    assert body["currency_code"] == "KZT"


def test_salon_context_missing_membership_403() -> None:
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    mock_repo.get_active_salon.return_value = _salon()
    mock_repo.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/auth/salons/{SALON_ID}/context",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "salon_access_denied"


def test_inactive_salon_rejected_404() -> None:
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    mock_repo.get_active_salon.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/auth/salons/{SALON_ID}/context",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404


def test_other_users_salon_403() -> None:
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    mock_repo.get_active_salon.return_value = SimpleNamespace(
        id=OTHER_SALON_ID,
        name="Other",
        slug="other",
        is_active=True,
    )
    mock_repo.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/auth/salons/{OTHER_SALON_ID}/context",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_role_from_db_not_token() -> None:
    """Token carries no role; membership mock defines admin."""
    app = create_app()
    token = _token_for()
    mock_repo = MagicMock()
    mock_repo.get_active_user_by_id.return_value = _user()
    mock_repo.get_active_salon.return_value = _salon()
    mock_repo.get_active_membership.return_value = _membership(role="receptionist")
    app.dependency_overrides[get_auth_repository] = lambda: mock_repo
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/auth/salons/{SALON_ID}/context",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.json()["role"] == "receptionist"


def test_rbac_owner_allowed() -> None:
    ctx = SalonContext(
        user_id=USER_ID,
        salon_id=SALON_ID,
        role="owner",
        salon_name="n",
        salon_slug="s",
        timezone="UTC",
        currency_code="KZT",
    )
    ensure_role_allowed(ctx, "owner", "admin")


def test_rbac_admin_allowed() -> None:
    ctx = SalonContext(
        user_id=USER_ID,
        salon_id=SALON_ID,
        role="admin",
        salon_name="n",
        salon_slug="s",
        timezone="UTC",
        currency_code="KZT",
    )
    ensure_role_allowed(ctx, "owner", "admin")


def test_rbac_staff_denied_for_owner_admin() -> None:
    ctx = SalonContext(
        user_id=USER_ID,
        salon_id=SALON_ID,
        role="staff",
        salon_name="n",
        salon_slug="s",
        timezone="UTC",
        currency_code="KZT",
    )
    with pytest.raises(ForbiddenRoleError):
        ensure_role_allowed(ctx, "owner", "admin")


def test_rbac_receptionist_denied_owner_only() -> None:
    ctx = SalonContext(
        user_id=USER_ID,
        salon_id=SALON_ID,
        role="receptionist",
        salon_name="n",
        salon_slug="s",
        timezone="UTC",
        currency_code="KZT",
    )
    with pytest.raises(ForbiddenRoleError):
        ensure_role_allowed(ctx, "owner")
