from __future__ import annotations

from unittest.mock import Mock

import pytest

from tests.postgres_safety import (
    PostgresTestSafetyError,
    create_guarded_engine,
)


def valid_test_environment() -> dict[str, str]:
    return {
        "LIMAN_PG_TESTS_ENABLED": "1",
        "LIMAN_PG_TEST_DATABASE_URL": (
            "postgresql+psycopg://liman_test_role:synthetic-pass@"
            "127.0.0.1:55432/liman_showcase_test_01"
        ),
        "LIMAN_PG_TEST_EXPECTED_DRIVER": "postgresql+psycopg",
        "LIMAN_PG_TEST_EXPECTED_HOST": "127.0.0.1",
        "LIMAN_PG_TEST_EXPECTED_PORT": "55432",
        "LIMAN_PG_TEST_EXPECTED_DATABASE": "liman_showcase_test_01",
        "LIMAN_PG_TEST_EXPECTED_USERNAME": "liman_test_role",
    }


def test_integration_database_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in valid_test_environment():
        monkeypatch.delenv(name, raising=False)
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError, match="disabled"):
        create_guarded_engine(engine_factory=factory)

    factory.assert_not_called()


def test_missing_allowlist_fails_without_using_application_database_url() -> None:
    factory = Mock()
    environment = {
        "LIMAN_PG_TESTS_ENABLED": "1",
        "DATABASE_URL": "postgresql+psycopg://production-role@127.0.0.1/production",
    }

    with pytest.raises(PostgresTestSafetyError, match="allowlist is incomplete"):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


@pytest.mark.parametrize(
    ("url", "expected_driver"),
    [
        (
            "postgresql+asyncpg://liman_test_role:synthetic-pass@"
            "127.0.0.1:55432/liman_showcase_test_01",
            "postgresql+psycopg",
        ),
        (
            "postgresql+psycopg://liman_test_role:synthetic-pass@"
            "127.0.0.1:55432/liman_showcase_test_01",
            "postgresql+asyncpg",
        ),
    ],
)
def test_wrong_driver_is_rejected(url: str, expected_driver: str) -> None:
    environment = valid_test_environment()
    environment["LIMAN_PG_TEST_DATABASE_URL"] = url
    environment["LIMAN_PG_TEST_EXPECTED_DRIVER"] = expected_driver
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError, match="driver"):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("LIMAN_PG_TEST_EXPECTED_HOST", "::1"),
        ("LIMAN_PG_TEST_EXPECTED_PORT", "55433"),
        ("LIMAN_PG_TEST_EXPECTED_DATABASE", "liman_showcase_test_02"),
        ("LIMAN_PG_TEST_EXPECTED_USERNAME", "another_test_role"),
    ],
)
def test_url_allowlist_mismatches_are_rejected(key: str, value: str) -> None:
    environment = valid_test_environment()
    environment[key] = value
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


@pytest.mark.parametrize(
    "key",
    [
        "LIMAN_PG_TEST_DATABASE_URL",
        "LIMAN_PG_TEST_EXPECTED_DRIVER",
        "LIMAN_PG_TEST_EXPECTED_HOST",
        "LIMAN_PG_TEST_EXPECTED_PORT",
        "LIMAN_PG_TEST_EXPECTED_DATABASE",
        "LIMAN_PG_TEST_EXPECTED_USERNAME",
    ],
)
def test_blank_allowlist_value_is_rejected(key: str) -> None:
    environment = valid_test_environment()
    environment[key] = "   "
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


@pytest.mark.parametrize(
    "database",
    [
        "production",
        "showcase_staging_test",
        "salon_prod_test",
        "stage_showcase_test",
        "showcase",
        "contest_database",
    ],
)
def test_ambiguous_or_deployment_database_names_are_rejected(database: str) -> None:
    environment = valid_test_environment()
    environment["LIMAN_PG_TEST_EXPECTED_DATABASE"] = database
    environment["LIMAN_PG_TEST_DATABASE_URL"] = (
        "postgresql+psycopg://liman_test_role:synthetic-pass@"
        f"127.0.0.1:55432/{database}"
    )
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError, match="database name"):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


@pytest.mark.parametrize("host", ["*", "0.0.0.0", "localhost", "192.0.2.10"])
def test_non_explicit_or_non_loopback_hosts_are_rejected(host: str) -> None:
    environment = valid_test_environment()
    environment["LIMAN_PG_TEST_EXPECTED_HOST"] = host
    environment["LIMAN_PG_TEST_DATABASE_URL"] = (
        "postgresql+psycopg://liman_test_role:synthetic-pass@"
        f"{host}:55432/liman_showcase_test_01"
    )
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


def test_rejected_url_never_appears_in_exception_text() -> None:
    environment = valid_test_environment()
    environment["LIMAN_PG_TEST_DATABASE_URL"] = (
        "postgresql+psycopg://liman_test_role:synthetic-private-value@"
        "127.0.0.1:55432/liman_showcase_production"
    )
    environment["LIMAN_PG_TEST_EXPECTED_DATABASE"] = "liman_showcase_production"
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError) as caught:
        create_guarded_engine(environ=environment, engine_factory=factory)

    assert "synthetic-private-value" not in str(caught.value)
    assert "postgresql+psycopg://" not in str(caught.value)
    factory.assert_not_called()


def test_engine_factory_failure_is_redacted() -> None:
    environment = valid_test_environment()

    def fail_with_url(url: object, **_: object) -> None:
        raise RuntimeError(f"engine failed for {url} synthetic-pass")

    with pytest.raises(PostgresTestSafetyError) as caught:
        create_guarded_engine(environ=environment, engine_factory=fail_with_url)

    assert "synthetic-pass" not in str(caught.value)
    assert "postgresql+psycopg://" not in str(caught.value)


def test_valid_url_creates_engine_only_after_explicit_opt_in() -> None:
    environment = valid_test_environment()
    sentinel_engine = object()
    factory = Mock(return_value=sentinel_engine)

    result = create_guarded_engine(environ=environment, engine_factory=factory)

    assert result is sentinel_engine
    factory.assert_called_once()
    url = factory.call_args.args[0]
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "127.0.0.1"
    assert url.port == 55432
    assert url.database == "liman_showcase_test_01"
    assert url.username == "liman_test_role"
    assert factory.call_args.kwargs == {"pool_pre_ping": True}


def test_non_exact_opt_in_flag_does_not_create_engine() -> None:
    environment = valid_test_environment()
    environment["LIMAN_PG_TESTS_ENABLED"] = "true"
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError, match="disabled"):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()


def test_username_must_be_an_explicit_test_role() -> None:
    environment = valid_test_environment()
    environment["LIMAN_PG_TEST_EXPECTED_USERNAME"] = "production_role"
    environment["LIMAN_PG_TEST_DATABASE_URL"] = (
        "postgresql+psycopg://production_role:synthetic-pass@"
        "127.0.0.1:55432/liman_showcase_test_01"
    )
    factory = Mock()

    with pytest.raises(PostgresTestSafetyError, match="test role"):
        create_guarded_engine(environ=environment, engine_factory=factory)

    factory.assert_not_called()
