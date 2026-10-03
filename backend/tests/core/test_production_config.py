"""Production settings validation (C19)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEV_BOOKING_MANAGE_TOKEN_PEPPER,
    DEV_JWT_SECRET_KEY,
    Settings,
    get_settings,
)


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://localhost:5432/liman_salon_test",
        "jwt_secret_key": "01234567890123456789012345678901",
        "booking_manage_token_pepper": "01234567890123456789012345678901",
        "environment": "development",
    }
    base.update(overrides)
    return Settings(**base)


def test_development_allows_dev_secret_defaults() -> None:
    s = _settings(
        jwt_secret_key=DEV_JWT_SECRET_KEY,
        booking_manage_token_pepper=DEV_BOOKING_MANAGE_TOKEN_PEPPER,
    )
    assert s.jwt_secret_key == DEV_JWT_SECRET_KEY


def test_production_rejects_dev_jwt_default() -> None:
    with pytest.raises(ValidationError, match="jwt_secret_key"):
        _settings(
            environment="production",
            jwt_secret_key=DEV_JWT_SECRET_KEY,
            booking_manage_token_pepper="01234567890123456789012345678901",
        )


def test_production_rejects_short_secrets() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        _settings(
            environment="production",
            jwt_secret_key="short",
            booking_manage_token_pepper="01234567890123456789012345678901",
        )


def test_production_accepts_strong_secrets() -> None:
    s = _settings(environment="staging", debug=False)
    assert s.environment == "staging"


def test_get_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://localhost/db")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", DEV_JWT_SECRET_KEY)
    monkeypatch.setenv("BOOKING_MANAGE_TOKEN_PEPPER", DEV_BOOKING_MANAGE_TOKEN_PEPPER)
    get_settings.cache_clear()
    assert get_settings().environment == "development"
