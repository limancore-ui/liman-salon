"""PostgreSQL integration for salon bonus settings (C20.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.db.models.salon import Salon
from app.db.session import engine
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL test database not reachable",
)


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _authed_client(
    db_session: Session,
    *,
    salon: Salon,
    role: str = "owner",
) -> tuple[TestClient, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon.id,
        name=salon.name,
        slug=salon.slug,
        is_active=True,
        timezone=salon.timezone,
        currency_code=salon.currency_code,
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon.id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def _seed_salon(session: Session) -> Salon:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Settings {suffix}",
        slug=f"settings-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
        settings={},
    )
    session.add(salon)
    session.flush()
    return salon


def _settings_url(salon_id: uuid.UUID) -> str:
    return f"/api/v1/salons/{salon_id}/settings"


def test_postgres_get_default_no_bonuses(db_session: Session) -> None:
    salon = _seed_salon(db_session)
    client, headers = _authed_client(db_session, salon=salon)
    try:
        response = client.get(_settings_url(salon.id), headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body == {"v": 1}
        assert "bonuses" not in body
    finally:
        client.close()


def test_postgres_patch_bonuses_persisted(db_session: Session) -> None:
    salon = _seed_salon(db_session)
    client, headers = _authed_client(db_session, salon=salon)
    try:
        patch = client.patch(
            _settings_url(salon.id),
            headers=headers,
            json={"bonuses": {"enabled": True, "earn_percentage": 5}},
        )
        assert patch.status_code == 200
        assert patch.json()["bonuses"] == {"enabled": True, "earn_percentage": 5}

        db_session.refresh(salon)
        assert salon.settings == {
            "v": 1,
            "bonuses": {"enabled": True, "earn_percentage": 5},
        }

        get_resp = client.get(_settings_url(salon.id), headers=headers)
        assert get_resp.json()["bonuses"]["enabled"] is True
    finally:
        client.close()


def test_postgres_patch_bonuses_disabled(db_session: Session) -> None:
    salon = _seed_salon(db_session)
    client, headers = _authed_client(db_session, salon=salon)
    try:
        response = client.patch(
            _settings_url(salon.id),
            headers=headers,
            json={"bonuses": {"enabled": False, "earn_percentage": 7.5}},
        )
        assert response.status_code == 200
        assert response.json()["bonuses"]["enabled"] is False
        db_session.refresh(salon)
        assert salon.settings["bonuses"]["enabled"] is False
    finally:
        client.close()


def test_postgres_cross_tenant_settings_forbidden(db_session: Session) -> None:
    salon_a = _seed_salon(db_session)
    salon_b = _seed_salon(db_session)
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )

    def _salon_lookup(salon_id: uuid.UUID) -> SimpleNamespace | None:
        if salon_id == salon_a.id:
            return SimpleNamespace(
                id=salon_a.id,
                name=salon_a.name,
                slug=salon_a.slug,
                is_active=True,
                timezone=salon_a.timezone,
                currency_code=salon_a.currency_code,
            )
        if salon_id == salon_b.id:
            return SimpleNamespace(
                id=salon_b.id,
                name=salon_b.name,
                slug=salon_b.slug,
                is_active=True,
                timezone=salon_b.timezone,
                currency_code=salon_b.currency_code,
            )
        return None

    mock_auth.get_active_salon.side_effect = _salon_lookup

    def _membership_lookup(salon_id: uuid.UUID, user_id: uuid.UUID) -> SimpleNamespace | None:
        if salon_id == salon_a.id and user_id == USER_ID:
            return SimpleNamespace(
                salon_id=salon_a.id,
                user_id=USER_ID,
                role="owner",
                is_active=True,
            )
        return None

    mock_auth.get_active_membership.side_effect = _membership_lookup

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = client.patch(
            _settings_url(salon_b.id),
            headers=headers,
            json={"bonuses": {"enabled": True, "earn_percentage": 5}},
        )
        assert response.status_code == 403
    finally:
        client.close()


def test_postgres_staff_cannot_patch_bonuses(db_session: Session) -> None:
    salon = _seed_salon(db_session)
    client, headers = _authed_client(db_session, salon=salon, role="staff")
    try:
        response = client.patch(
            _settings_url(salon.id),
            headers=headers,
            json={"bonuses": {"enabled": True, "earn_percentage": 5}},
        )
        assert response.status_code == 403
    finally:
        client.close()
