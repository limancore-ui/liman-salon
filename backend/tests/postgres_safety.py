"""Fail-closed helpers for explicitly enabled PostgreSQL integration tests.

This module deliberately does not load application settings, ``DATABASE_URL``,
or dotenv files. Integration tests must create their engine through
``create_guarded_engine`` before making database sessions or connections.
"""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import Any

from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker


class PostgresTestSafetyError(RuntimeError):
    """Raised when an integration-test database target is not allowlisted."""


_SESSION_MODULE_NAME = "app.db.session"
_SAFE_PREIMPORT_MODULES = {"app", "app.core", "app.core.config"}
_GLOBAL_ACCESS_ERROR = (
    "Application-global database access is disabled in the PostgreSQL test harness."
)
_ISOLATED_TEST_SETTINGS = SimpleNamespace(
    app_name="Liman Salon isolated PostgreSQL tests",
    debug=False,
    jwt_secret_key="local-test-only-placeholder",
    jwt_algorithm="HS256",
    access_token_expire_seconds=900,
    booking_manage_token_pepper="local-test-only-placeholder",
    public_booking_hold_seconds=300,
    media_max_upload_bytes=5_242_880,
)


_ENABLE_FLAG = "LIMAN_PG_TESTS_ENABLED"
_DATABASE_URL = "LIMAN_PG_TEST_DATABASE_URL"
_EXPECTED_DRIVER = "LIMAN_PG_TEST_EXPECTED_DRIVER"
_EXPECTED_HOST = "LIMAN_PG_TEST_EXPECTED_HOST"
_EXPECTED_PORT = "LIMAN_PG_TEST_EXPECTED_PORT"
_EXPECTED_DATABASE = "LIMAN_PG_TEST_EXPECTED_DATABASE"
_EXPECTED_USERNAME = "LIMAN_PG_TEST_EXPECTED_USERNAME"

_REQUIRED_ALLOWLIST = (
    _DATABASE_URL,
    _EXPECTED_DRIVER,
    _EXPECTED_HOST,
    _EXPECTED_PORT,
    _EXPECTED_DATABASE,
    _EXPECTED_USERNAME,
)
_EXPECTED_POSTGRES_DRIVER = "postgresql+psycopg"
_SAFE_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]+\Z")
_TEST_NAME_MARKER = re.compile(r"(?:^|[_-])test(?:$|[_-])", re.IGNORECASE)
_DEPLOYMENT_NAME_MARKER = re.compile(r"prod|stag", re.IGNORECASE)
_ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "::1"}


def _required_value(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: required test configuration is missing or blank."
        )
    return value


def _validate_database_name(name: str) -> None:
    if (
        not name
        or not _SAFE_IDENTIFIER.fullmatch(name)
        or not _TEST_NAME_MARKER.search(name)
        or _DEPLOYMENT_NAME_MARKER.search(name)
    ):
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: database name is not an allowed test database."
        )


def _validate_username(name: str) -> None:
    if (
        not name
        or not _SAFE_IDENTIFIER.fullmatch(name)
        or not _TEST_NAME_MARKER.search(name)
        or _DEPLOYMENT_NAME_MARKER.search(name)
    ):
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: username is not an allowed test role."
        )


def _validated_test_url(environment: Mapping[str, str]) -> URL:
    if environment.get(_ENABLE_FLAG) != "1":
        raise PostgresTestSafetyError(
            "PostgreSQL integration tests are disabled; explicit test-only opt-in is required."
        )

    if any(
        not isinstance(environment.get(name), str)
        or not environment[name].strip()
        for name in _REQUIRED_ALLOWLIST
    ):
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: the explicit connection allowlist is incomplete."
        )

    values = {name: _required_value(environment, name) for name in _REQUIRED_ALLOWLIST}
    if values[_EXPECTED_DRIVER] != _EXPECTED_POSTGRES_DRIVER:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: only the approved PostgreSQL driver is allowed."
        )

    expected_host = values[_EXPECTED_HOST]
    try:
        parsed_expected_host = str(ipaddress.ip_address(expected_host))
    except ValueError:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: expected host must be an explicit loopback IP."
        ) from None
    if parsed_expected_host not in _ALLOWED_LOOPBACK_HOSTS:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: only an explicit loopback host is allowed."
        )

    try:
        expected_port = int(values[_EXPECTED_PORT], 10)
    except ValueError:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: expected port must be an explicit TCP port."
        ) from None
    if str(expected_port) != values[_EXPECTED_PORT] or not 1 <= expected_port <= 65535:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: expected port is outside the valid range."
        )

    expected_database = values[_EXPECTED_DATABASE]
    expected_username = values[_EXPECTED_USERNAME]
    _validate_database_name(expected_database)
    _validate_username(expected_username)

    try:
        url = make_url(values[_DATABASE_URL])
        url_host = str(ipaddress.ip_address(url.host or ""))
        url_port = url.port
    except Exception:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: database URL is invalid; connection details are redacted."
        ) from None

    if url.drivername != values[_EXPECTED_DRIVER]:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: URL driver does not match the allowlist."
        )
    if url_host not in _ALLOWED_LOOPBACK_HOSTS or url_host != parsed_expected_host:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: URL host does not match the loopback allowlist."
        )
    if url_port != expected_port:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: URL port does not match the allowlist."
        )
    if url.database != expected_database:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: URL database does not match the allowlist."
        )
    if url.username != expected_username:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: URL username does not match the allowlist."
        )
    if url.query:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard: URL query options are not allowed."
        )

    return url


def create_guarded_engine(
    *,
    environ: Mapping[str, str] | None = None,
    engine_factory: Callable[..., Any] | None = None,
) -> Any:
    """Create an engine only after explicit test-mode and target validation.

    ``engine_factory`` exists for isolated unit tests. Production integration
    tests should omit it and must not import the application's global engine.
    """

    environment = os.environ if environ is None else environ
    url = _validated_test_url(environment)

    if engine_factory is None:
        from sqlalchemy import create_engine

        engine_factory = create_engine

    try:
        return engine_factory(url, pool_pre_ping=True)
    except Exception:
        raise PostgresTestSafetyError(
            "PostgreSQL test engine could not be created; connection details are redacted."
        ) from None


class _BlockedApplicationDatabaseAccess:
    """Fail closed when code reaches application-global DB objects."""

    def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
        raise PostgresTestSafetyError(_GLOBAL_ACCESS_ERROR)

    def __getattr__(self, _name: str) -> Any:
        raise PostgresTestSafetyError(_GLOBAL_ACCESS_ERROR)


class _GuardedSessionProvider:
    def __init__(
        self,
        engine: Any,
        *,
        sessionmaker_factory: Callable[..., Any] = sessionmaker,
    ) -> None:
        self._enabled = True
        self._session_factory = sessionmaker_factory(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )

    def get_db(self):
        if not self._enabled:
            raise PostgresTestSafetyError(_GLOBAL_ACCESS_ERROR)

        db = self._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def disable(self) -> None:
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled


def _application_imports_started(module_table: Any) -> bool:
    return any(
        name.startswith("app.") and name not in _SAFE_PREIMPORT_MODULES
        for name in module_table
    )


def _blocked_get_db():
    raise PostgresTestSafetyError(
        "FastAPI get_db must be overridden by the guarded PostgreSQL test harness."
    )


def _blocked_engine_factory(*_args: Any, **_kwargs: Any) -> Any:
    raise PostgresTestSafetyError(
        "Direct SQLAlchemy engine creation is disabled; use the guarded test engine."
    )


def block_unapproved_engine_creation(
    *,
    target_modules: tuple[Any, ...] | None = None,
) -> list[tuple[Any, Any]]:
    """Block standard SQLAlchemy create_engine entry points after guard setup."""

    if target_modules is None:
        from importlib import import_module

        import sqlalchemy
        from sqlalchemy import engine as sqlalchemy_engine

        target_modules = (
            sqlalchemy,
            sqlalchemy_engine,
            import_module("sqlalchemy.engine.create"),
        )

    patches: list[_AttributePatch] = []
    try:
        for module in target_modules:
            original = getattr(module, "create_engine", None)
            if original is None:
                continue
            patch = _AttributePatch(
                module=module,
                attribute="create_engine",
                original=original,
                replacement=_blocked_engine_factory,
            )
            # Record before setattr: a custom module may mutate then raise.
            patches.append(patch)
            setattr(module, patch.attribute, patch.replacement)
            if getattr(module, patch.attribute, None) is not patch.replacement:
                raise RuntimeError("Engine factory replacement did not stick.")
    except BaseException as error:
        try:
            restore_engine_creation(patches)
        except Exception:
            raise PostgresTestSafetyError(
                "PostgreSQL test safety guard could not roll back engine factory patches."
            ) from None
        if not isinstance(error, Exception):
            raise
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard could not install engine factory patches."
        ) from None
    return patches


@dataclass(frozen=True)
class _AttributePatch:
    module: Any
    attribute: str
    original: Any
    replacement: Any


def restore_engine_creation(patches: list[_AttributePatch]) -> None:
    """Restore only attributes that still contain this guard's replacement."""

    failures = False
    for patch in reversed(patches):
        try:
            if getattr(patch.module, patch.attribute, None) is patch.replacement:
                setattr(patch.module, patch.attribute, patch.original)
        except Exception:
            failures = True
    if failures:
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard could not fully restore engine factory patches."
        ) from None


def require_guard_for_postgres_test_file(file_name: str, runtime_ready: bool) -> None:
    """Require the explicit plugin for files using the ``*_postgres.py`` convention."""

    if file_name.endswith("_postgres.py") and not runtime_ready:
        raise PostgresTestSafetyError(
            "PostgreSQL integration files require the pre-import safety plugin."
        )


def install_isolated_test_settings(config_module: Any | None = None) -> tuple[Any, Any, Any]:
    """Avoid loading application settings or dotenv files in guarded test runs."""

    if config_module is None:
        from app.core import config as config_module

    original_get_settings = config_module.get_settings

    def get_isolated_test_settings() -> Any:
        return _ISOLATED_TEST_SETTINGS

    try:
        config_module.get_settings = get_isolated_test_settings
        if config_module.get_settings is not get_isolated_test_settings:
            raise RuntimeError("Settings replacement did not stick.")
    except BaseException as error:
        try:
            if config_module.get_settings is get_isolated_test_settings:
                config_module.get_settings = original_get_settings
        except Exception:
            raise PostgresTestSafetyError(
                "PostgreSQL test safety guard could not roll back isolated settings."
            ) from None
        if not isinstance(error, Exception):
            raise
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard could not install isolated settings."
        ) from None
    return config_module, original_get_settings, get_isolated_test_settings


def restore_isolated_test_settings(patch: tuple[Any, Any, Any]) -> None:
    config_module, original_get_settings, isolated_get_settings = patch
    if config_module.get_settings is isolated_get_settings:
        config_module.get_settings = original_get_settings


def install_guarded_session_module(
    engine: Any,
    *,
    modules: Any | None = None,
    sessionmaker_factory: Callable[..., Any] = sessionmaker,
) -> ModuleType:
    """Install a test-only app.db.session shim before application imports.

    The shim exposes a deny-by-default FastAPI dependency and blocked aliases
    for the application's global ``engine`` and ``SessionLocal``. The guarded
    dependency creates sessions from the engine returned by
    ``create_guarded_engine``.
    """

    module_table = sys.modules if modules is None else modules
    if _application_imports_started(module_table):
        raise PostgresTestSafetyError(
            "PostgreSQL test harness must be installed before application imports."
        )

    provider = _GuardedSessionProvider(
        engine,
        sessionmaker_factory=sessionmaker_factory,
    )
    module = ModuleType(_SESSION_MODULE_NAME)
    module.__dict__.update(
        {
            "__liman_guarded_postgres_test_module__": True,
            "__liman_guarded_session_provider__": provider,
            "get_db": _blocked_get_db,
            "guarded_get_db": provider.get_db,
            "engine": _BlockedApplicationDatabaseAccess(),
            "SessionLocal": _BlockedApplicationDatabaseAccess(),
        }
    )
    try:
        module_table[_SESSION_MODULE_NAME] = module
        if module_table.get(_SESSION_MODULE_NAME) is not module:
            raise RuntimeError("Session shim registration did not stick.")
    except BaseException as error:
        try:
            if module_table.get(_SESSION_MODULE_NAME) is module:
                del module_table[_SESSION_MODULE_NAME]
        except Exception:
            raise PostgresTestSafetyError(
                "PostgreSQL test safety guard could not roll back the session shim."
            ) from None
        if not isinstance(error, Exception):
            raise
        raise PostgresTestSafetyError(
            "PostgreSQL test safety guard could not install the session shim."
        ) from None
    return module


def configure_guarded_postgres_runtime(
    *,
    environ: Mapping[str, str] | None = None,
    engine_factory: Callable[..., Any] = create_guarded_engine,
    modules: Any | None = None,
    sessionmaker_factory: Callable[..., Any] = sessionmaker,
) -> tuple[Any, ModuleType]:
    """Validate and create the guarded engine before installing app imports."""

    module_table = sys.modules if modules is None else modules
    if _application_imports_started(module_table):
        raise PostgresTestSafetyError(
            "PostgreSQL test harness must be installed before application imports."
        )

    engine = engine_factory(environ=environ)
    try:
        module = install_guarded_session_module(
            engine,
            modules=module_table,
            sessionmaker_factory=sessionmaker_factory,
        )
    except BaseException:
        engine.dispose()
        raise
    return engine, module


def install_guarded_get_db_override(app: Any, session_module: ModuleType) -> dict[Any, Any]:
    """Override FastAPI's guarded dependency with its guarded session provider."""

    if not getattr(session_module, "__liman_guarded_postgres_test_module__", False):
        raise PostgresTestSafetyError(
            "FastAPI database override requires the guarded test session module."
        )

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[session_module.get_db] = session_module.guarded_get_db
    return previous_overrides
