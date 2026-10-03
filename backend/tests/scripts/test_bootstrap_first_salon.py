"""Guards and idempotency helpers for first-salon bootstrap (C19)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_first_salon.py"


def _load_bootstrap_module():
    spec = importlib.util.spec_from_file_location("bootstrap_first_salon", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bootstrap():
    return _load_bootstrap_module()


def test_production_requires_allow_flag(bootstrap) -> None:
    with pytest.raises(SystemExit, match="ALLOW_FIRST_SALON_BOOTSTRAP"):
        bootstrap.assert_bootstrap_allowed(
            environment="production",
            database_url="postgresql+psycopg://x/y/liman_salon",
            allow_bootstrap=False,
        )


def test_production_refuses_test_database(bootstrap) -> None:
    with pytest.raises(SystemExit, match="liman_salon_test"):
        bootstrap.assert_bootstrap_allowed(
            environment="production",
            database_url="postgresql+psycopg://x/y/liman_salon_test",
            allow_bootstrap=True,
        )


def test_development_skips_allow_flag(bootstrap) -> None:
    bootstrap.assert_bootstrap_allowed(
        environment="development",
        database_url="postgresql+psycopg://x/y/liman_salon_test",
        allow_bootstrap=False,
    )


def test_database_name_from_url(bootstrap) -> None:
    assert (
        bootstrap.database_name_from_url("postgresql+psycopg://u:p@h:5432/my_db?ssl=1")
        == "my_db"
    )


def test_bootstrap_idempotent_on_postgres(bootstrap) -> None:
    from app.core.config import get_settings
    from app.db.models.salon import Salon
    from app.db.models.salon_user import SalonUser
    from app.db.models.user import User
    from app.db.session import engine
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL test database not reachable")

    get_settings.cache_clear()
    suffix = __import__("uuid").uuid4().hex[:8]
    email = f"bootstrap-{suffix}@example.com"
    slug = f"bootstrap-{suffix}"

    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        from app.core.security import normalize_email

        user, user_action = bootstrap._get_or_create_user(
            session,
            email=email,
            full_name="Bootstrap Test",
            password="01234567890123456789012345678901",
        )
        assert user_action == "created"
        user2, user_action2 = bootstrap._get_or_create_user(
            session,
            email=email,
            full_name="Bootstrap Test",
            password="different-password",
        )
        assert user_action2 == "reused"
        assert user2.id == user.id

        salon, salon_action = bootstrap._get_or_create_salon(
            session,
            name="Bootstrap Salon",
            slug=slug,
            timezone="UTC",
            currency_code="USD",
        )
        assert salon_action == "created"
        membership = bootstrap._ensure_owner_membership(
            session,
            salon_id=salon.id,
            user_id=user.id,
        )
        assert membership == "created"
        membership2 = bootstrap._ensure_owner_membership(
            session,
            salon_id=salon.id,
            user_id=user.id,
        )
        assert membership2 == "reused"

        normalized = normalize_email(email)
        assert (
            session.scalar(select(User).where(func.lower(User.email) == normalized))
            is not None
        )
        assert session.scalar(select(Salon).where(Salon.slug == slug)) is not None
        assert (
            session.scalar(
                select(SalonUser).where(
                    SalonUser.salon_id == salon.id,
                    SalonUser.user_id == user.id,
                    SalonUser.role == "owner",
                )
            )
            is not None
        )
    finally:
        session.close()
        transaction.rollback()
        connection.close()
