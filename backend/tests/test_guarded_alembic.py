from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.engine import make_url

from tests.guarded_alembic import GuardedAlembicError, run_guarded_upgrade
from tests.postgres_safety import PostgresTestSafetyError

_TEST_URL = (
    "postgresql+psycopg://liman_test_role:synthetic-pass@"
    "127.0.0.1:55432/liman_showcase_test_01"
)


def valid_test_environment() -> dict[str, str]:
    return {
        "LIMAN_PG_TESTS_ENABLED": "1",
        "LIMAN_PG_TEST_DATABASE_URL": _TEST_URL,
        "LIMAN_PG_TEST_EXPECTED_DRIVER": "postgresql+psycopg",
        "LIMAN_PG_TEST_EXPECTED_HOST": "127.0.0.1",
        "LIMAN_PG_TEST_EXPECTED_PORT": "55432",
        "LIMAN_PG_TEST_EXPECTED_DATABASE": "liman_showcase_test_01",
        "LIMAN_PG_TEST_EXPECTED_USERNAME": "liman_test_role",
    }


class FakeConnection:
    def __init__(self, identity: tuple[Any, Any, Any]) -> None:
        self.identity = identity
        self.executed: list[str] = []
        self.rollback_calls = 0
        self.close_calls = 0

    def execute(self, statement: Any) -> Any:
        self.executed.append(str(statement))
        return FakeResult(self.identity)

    def rollback(self) -> None:
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1


class FakeResult:
    def __init__(self, row: tuple[Any, Any, Any]) -> None:
        self._row = row

    def one(self) -> tuple[Any, Any, Any]:
        return self._row


class FakeEngine:
    def __init__(self, url: Any, connection: FakeConnection) -> None:
        self.url = url
        self.connection = connection
        self.connect_calls = 0
        self.dispose_calls = 0

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        return self.connection

    def dispose(self) -> None:
        self.dispose_calls += 1


class FakeConfig:
    def __init__(self, path: str) -> None:
        self.path = path
        self.attributes: dict[str, Any] = {}


def _run_with_fakes(
    *,
    environment: dict[str, str] | None = None,
    identity: tuple[Any, Any, Any] = (
        "liman_showcase_test_01",
        "liman_test_role",
        55432,
    ),
    upgrade_command: Callable[[Any, str], Any] | None = None,
) -> tuple[FakeEngine, FakeConnection, list[tuple[FakeConfig, str]]]:
    selected_environment = valid_test_environment() if environment is None else environment
    connection = FakeConnection(identity)
    created: list[FakeEngine] = []
    calls: list[tuple[FakeConfig, str]] = []

    def engine_factory(url: Any, **_kwargs: Any) -> FakeEngine:
        engine = FakeEngine(url, connection)
        created.append(engine)
        return engine

    def config_factory(path: str) -> FakeConfig:
        return FakeConfig(path)

    def upgrade(config: FakeConfig, revision: str) -> None:
        calls.append((config, revision))
        if upgrade_command is not None:
            upgrade_command(config, revision)

    run_guarded_upgrade(
        config_path="alembic.ini",
        environ=selected_environment,
        engine_factory=engine_factory,
        config_factory=config_factory,
        upgrade_command=upgrade,
    )
    assert len(created) == 1
    return created[0], connection, calls


@pytest.mark.parametrize(
    ("key", "expected_value", "url_value", "url_field"),
    [
        ("LIMAN_PG_TEST_EXPECTED_HOST", "localhost", "localhost", "host"),
        (
            "LIMAN_PG_TEST_EXPECTED_DATABASE",
            "liman_production",
            "liman_production",
            "database",
        ),
        ("LIMAN_PG_TEST_EXPECTED_USERNAME", "postgres", "postgres", "username"),
        ("LIMAN_PG_TEST_EXPECTED_PORT", "55433", "55432", "port"),
    ],
)
def test_invalid_allowlist_is_rejected_before_engine_or_migration(
    key: str, expected_value: str, url_value: str, url_field: str
) -> None:
    environment = valid_test_environment()
    environment[key] = expected_value
    parsed = make_url(environment["LIMAN_PG_TEST_DATABASE_URL"])
    parsed = parsed.set(**{url_field: url_value})
    environment["LIMAN_PG_TEST_DATABASE_URL"] = parsed.render_as_string(
        hide_password=False
    )
    factory_calls: list[Any] = []
    migration_calls: list[Any] = []

    def engine_factory(url: Any, **kwargs: Any) -> Any:
        factory_calls.append((url, kwargs))
        raise AssertionError("invalid allowlist must fail before engine creation")

    with pytest.raises(PostgresTestSafetyError):
        run_guarded_upgrade(
            environ=environment,
            engine_factory=engine_factory,
            upgrade_command=lambda *args: migration_calls.append(args),
        )

    assert factory_calls == []
    assert migration_calls == []


@pytest.mark.parametrize(
    "identity",
    [
        ("other_test_database", "liman_test_role", 55432),
        ("liman_showcase_test_01", "other_test_role", 55432),
        ("liman_showcase_test_01", "liman_test_role", 5432),
    ],
)
def test_preflight_identity_mismatch_blocks_migration_and_cleans_up(
    identity: tuple[Any, Any, Any],
) -> None:
    connection = FakeConnection(identity)
    engines: list[FakeEngine] = []
    migrations: list[Any] = []

    def engine_factory(url: Any, **_kwargs: Any) -> FakeEngine:
        engine = FakeEngine(url, connection)
        engines.append(engine)
        return engine

    with pytest.raises(GuardedAlembicError, match="identity"):
        run_guarded_upgrade(
            environ=valid_test_environment(),
            engine_factory=engine_factory,
            upgrade_command=lambda *args: migrations.append(args),
        )

    assert migrations == []
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1
    assert len(engines) == 1 and engines[0].dispose_calls == 1


def test_same_preflight_connection_is_passed_to_alembic_and_cleaned_up() -> None:
    engine, connection, calls = _run_with_fakes()

    assert len(calls) == 1
    config, revision = calls[0]
    assert revision == "head"
    assert config.attributes["connection"] is connection
    assert connection.rollback_calls == 1
    assert connection.close_calls == 1
    assert engine.dispose_calls == 1
    assert len(connection.executed) == 1
    assert connection.executed[0].lstrip().upper().startswith("SELECT")


def test_resources_are_cleaned_and_driver_error_is_redacted_on_upgrade_failure() -> None:
    private_marker = "synthetic-private-marker"
    connection = FakeConnection(
        ("liman_showcase_test_01", "liman_test_role", 55432)
    )
    engines: list[FakeEngine] = []

    def engine_factory(url: Any, **_kwargs: Any) -> FakeEngine:
        engine = FakeEngine(url, connection)
        engines.append(engine)
        return engine

    def fail_upgrade(_config: FakeConfig, _revision: str) -> None:
        raise RuntimeError(f"driver failure contained {private_marker}")

    with pytest.raises(GuardedAlembicError) as raised:
        run_guarded_upgrade(
            environ=valid_test_environment(),
            engine_factory=engine_factory,
            config_factory=FakeConfig,
            upgrade_command=fail_upgrade,
        )

    assert private_marker not in str(raised.value)
    assert connection.close_calls == 1
    assert len(engines) == 1 and engines[0].dispose_calls == 1


def test_missing_allowlist_does_not_create_engine_or_run_migrations() -> None:
    engine_calls: list[Any] = []
    migration_calls: list[Any] = []

    with pytest.raises(PostgresTestSafetyError):
        run_guarded_upgrade(
            environ={},
            engine_factory=lambda *args, **kwargs: engine_calls.append((args, kwargs)),
            upgrade_command=lambda *args: migration_calls.append(args),
        )

    assert engine_calls == []
    assert migration_calls == []
