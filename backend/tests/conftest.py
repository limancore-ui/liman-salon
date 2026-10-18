"""Test bootstrap: DB URL before app.db.session imports the engine."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://localhost:5432/liman_salon_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "01234567890123456789012345678901",
)

from app.core.config import get_settings

get_settings.cache_clear()


@pytest.fixture(scope="session")
def postgres_test_engine(request):
    """Expose only the engine prepared by the explicit pre-import plugin."""

    from tests.postgres_safety import PostgresTestSafetyError

    engine = getattr(request.config, "_liman_postgres_test_engine", None)
    if engine is None:
        raise PostgresTestSafetyError(
            "Load tests.postgres_safety_plugin for PostgreSQL integration tests."
        )
    return engine


@pytest.fixture
def postgres_test_app(request, postgres_test_engine):
    """Create an app whose FastAPI database dependency uses the guarded engine."""

    from app.db import session as session_module
    from app.main import create_app
    from tests.postgres_safety import install_guarded_get_db_override

    application = create_app()
    previous_overrides = install_guarded_get_db_override(application, session_module)
    try:
        yield application
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(previous_overrides)


def pytest_collect_file(file_path, parent):
    """Require the pre-import guard for tests using the *_postgres.py convention."""

    name = getattr(file_path, "name", str(file_path).rsplit("/", 1)[-1])
    from tests.postgres_safety import (
        PostgresTestSafetyError,
        require_guard_for_postgres_test_file,
    )

    try:
        require_guard_for_postgres_test_file(
            name,
            runtime_ready=hasattr(parent.config, "_liman_postgres_test_engine"),
        )
    except PostgresTestSafetyError as error:
        raise pytest.UsageError(
            f"{error} Load tests.postgres_safety_plugin with the explicit allowlist."
        ) from None
