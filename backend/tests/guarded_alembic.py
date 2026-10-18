"""Run Alembic against the explicitly guarded PostgreSQL test target."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from tests.postgres_safety import PostgresTestSafetyError, create_guarded_engine

_EXPECTED_DATABASE = "LIMAN_PG_TEST_EXPECTED_DATABASE"
_EXPECTED_USERNAME = "LIMAN_PG_TEST_EXPECTED_USERNAME"
_EXPECTED_PORT = "LIMAN_PG_TEST_EXPECTED_PORT"
_IDENTITY_QUERY = text(
    "SELECT current_database(), current_user, inet_server_port()"
)


class GuardedAlembicError(RuntimeError):
    """A redacted failure from the guarded Alembic runner."""


def _verify_target_identity(connection: Any, url: Any) -> None:
    try:
        row = connection.execute(_IDENTITY_QUERY).one()
        actual = (row[0], row[1], int(row[2]) if row[2] is not None else None)
        expected = (url.database, url.username, url.port)
        if actual != expected:
            raise GuardedAlembicError(
                "PostgreSQL preflight identity does not match the guarded target."
            )
    except GuardedAlembicError:
        raise
    except Exception:
        raise GuardedAlembicError(
            "PostgreSQL preflight failed; connection details are redacted."
        ) from None
    finally:
        try:
            # End the read-only preflight transaction before Alembic owns the connection.
            connection.rollback()
        except Exception:
            raise GuardedAlembicError(
                "PostgreSQL preflight cleanup failed; connection details are redacted."
            ) from None


def run_guarded_upgrade(
    *,
    config_path: str | Path | None = None,
    revision: str = "head",
    environ: Mapping[str, str] | None = None,
    engine_factory: Callable[..., Any] | None = None,
    config_factory: Callable[[str], Any] | None = None,
    upgrade_command: Callable[[Any, str], Any] | None = None,
) -> None:
    """Validate, preflight, and migrate using the same guarded connection."""

    environment = os.environ if environ is None else environ
    if revision != "head":
        raise GuardedAlembicError("Only the approved Alembic target 'head' is allowed.")

    selected_config_path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).resolve().parents[1] / "alembic.ini"
    )
    selected_config_factory = Config if config_factory is None else config_factory
    selected_upgrade_command = (
        command.upgrade if upgrade_command is None else upgrade_command
    )

    engine = None
    connection = None
    failed = False
    try:
        # create_guarded_engine validates opt-in and the entire allowlist before
        # invoking SQLAlchemy's engine factory or opening a connection.
        engine = create_guarded_engine(
            environ=environment,
            engine_factory=engine_factory,
        )
        connection = engine.connect()
        _verify_target_identity(connection, engine.url)

        expected_identity = (
            environment.get(_EXPECTED_DATABASE),
            environment.get(_EXPECTED_USERNAME),
            int(environment[_EXPECTED_PORT]),
        )
        url_identity = (engine.url.database, engine.url.username, engine.url.port)
        if expected_identity != url_identity:
            raise GuardedAlembicError(
                "PostgreSQL URL identity does not match the explicit test allowlist."
            )

        alembic_config = selected_config_factory(str(selected_config_path))
        alembic_config.attributes["connection"] = connection
        selected_upgrade_command(alembic_config, revision)
    except PostgresTestSafetyError:
        failed = True
        raise
    except GuardedAlembicError:
        failed = True
        raise
    except BaseException as error:
        failed = True
        if not isinstance(error, Exception):
            raise
        raise GuardedAlembicError(
            "Guarded Alembic upgrade failed; connection details are redacted."
        ) from None
    finally:
        try:
            if connection is not None:
                connection.close()
        except Exception:
            if not failed:
                raise GuardedAlembicError(
                    "Guarded Alembic connection cleanup failed."
                ) from None
        finally:
            try:
                if engine is not None:
                    engine.dispose()
            except Exception:
                if not failed:
                    raise GuardedAlembicError(
                        "Guarded Alembic engine cleanup failed."
                    ) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", nargs="?", choices=("head",), default="head")
    args = parser.parse_args(argv)
    try:
        run_guarded_upgrade(revision=args.revision)
    except (GuardedAlembicError, PostgresTestSafetyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
