"""Guards, idempotency, and catalog links for staging demo seed."""

from __future__ import annotations

import importlib.util
import sys
from datetime import time
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "seed_staging_demo.py"
TEST_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "seed_public_booking_test.py"
)

STAGING_URL = "postgresql+psycopg://u:p@db:5432/liman_salon_staging"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def staging_seed():
    return _load_module(SCRIPT_PATH, "seed_staging_demo")


@pytest.fixture(scope="module")
def test_db_seed():
    return _load_module(TEST_SEED_PATH, "seed_public_booking_test")


def test_database_name_from_url(staging_seed) -> None:
    assert (
        staging_seed.database_name_from_url(
            "postgresql+psycopg://u:p@h:5432/liman_salon_staging?ssl=1"
        )
        == "liman_salon_staging"
    )


def test_refuses_non_staging_environment(staging_seed) -> None:
    with pytest.raises(SystemExit, match="ENVIRONMENT must be 'staging'"):
        staging_seed.assert_staging_demo_allowed(
            environment="production",
            database_url=STAGING_URL,
            allow_seed=True,
        )


def test_refuses_development_even_with_allow(staging_seed) -> None:
    with pytest.raises(SystemExit, match="ENVIRONMENT must be 'staging'"):
        staging_seed.assert_staging_demo_allowed(
            environment="development",
            database_url=STAGING_URL,
            allow_seed=True,
        )


def test_staging_requires_allow_flag(staging_seed) -> None:
    with pytest.raises(SystemExit, match="ALLOW_STAGING_DEMO_SEED"):
        staging_seed.assert_staging_demo_allowed(
            environment="staging",
            database_url=STAGING_URL,
            allow_seed=False,
        )


def test_staging_refuses_wrong_database_name(staging_seed) -> None:
    with pytest.raises(SystemExit, match="liman_salon_staging"):
        staging_seed.assert_staging_demo_allowed(
            environment="staging",
            database_url="postgresql+psycopg://u:p@db:5432/liman_salon",
            allow_seed=True,
        )


def test_staging_refuses_test_database_name(staging_seed) -> None:
    with pytest.raises(SystemExit, match="liman_salon_staging"):
        staging_seed.assert_staging_demo_allowed(
            environment="staging",
            database_url="postgresql+psycopg://u:p@db:5432/liman_salon_test",
            allow_seed=True,
        )


def test_staging_allows_exact_guards(staging_seed) -> None:
    staging_seed.assert_staging_demo_allowed(
        environment="staging",
        database_url="postgresql+psycopg://u:p@db:5432/liman_salon_staging",
        allow_seed=True,
    )


def test_refuses_empty_environment(staging_seed) -> None:
    with pytest.raises(SystemExit, match="ENVIRONMENT must be 'staging'"):
        staging_seed.assert_staging_demo_allowed(
            environment="",
            database_url=STAGING_URL,
            allow_seed=True,
        )


def test_refuses_unknown_environment(staging_seed) -> None:
    with pytest.raises(SystemExit, match="ENVIRONMENT must be 'staging'"):
        staging_seed.assert_staging_demo_allowed(
            environment="qa",
            database_url=STAGING_URL,
            allow_seed=True,
        )


def test_staging_refuses_empty_database_url(staging_seed) -> None:
    with pytest.raises(SystemExit, match="liman_salon_staging"):
        staging_seed.assert_staging_demo_allowed(
            environment="staging",
            database_url="",
            allow_seed=True,
        )


def test_staging_refuses_similar_database_name(staging_seed) -> None:
    with pytest.raises(SystemExit, match="liman_salon_staging"):
        staging_seed.assert_staging_demo_allowed(
            environment="staging",
            database_url="postgresql+psycopg://u:p@db:5432/liman_salon_staging_backup",
            allow_seed=True,
        )


def test_staging_allows_database_url_with_query_params(staging_seed) -> None:
    staging_seed.assert_staging_demo_allowed(
        environment="staging",
        database_url=f"{STAGING_URL}?sslmode=require&application_name=seed",
        allow_seed=True,
    )


class _StubSessionLocalCalled(Exception):
    """Raised by the stubbed session factory instead of opening a DB session."""


@pytest.fixture
def stubbed_seed_env(monkeypatch):
    # Import before env is patched so the module-level engine keeps the test URL;
    # creating the engine does not connect.
    import app.db.session as db_session
    from app.core.config import get_settings

    calls: list[tuple[tuple, dict]] = []

    def _stub_session_local(*args, **kwargs):
        calls.append((args, kwargs))
        raise _StubSessionLocalCalled

    monkeypatch.setattr(db_session, "SessionLocal", _stub_session_local)

    def _apply(*, environment: str, database_url: str, allow: str | None) -> None:
        monkeypatch.setenv("ENVIRONMENT", environment)
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.setenv("JWT_SECRET_KEY", "seed-staging-demo-test-jwt-secret-0123456789")
        monkeypatch.setenv(
            "BOOKING_MANAGE_TOKEN_PEPPER", "seed-staging-demo-test-pepper-0123456789"
        )
        if allow is None:
            monkeypatch.delenv("ALLOW_STAGING_DEMO_SEED", raising=False)
        else:
            monkeypatch.setenv("ALLOW_STAGING_DEMO_SEED", allow)

    yield calls, _apply
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("environment", "database_url", "allow"),
    [
        ("", STAGING_URL, "1"),
        ("qa", STAGING_URL, "1"),
        ("production", STAGING_URL, "1"),
        ("staging", STAGING_URL, None),
        ("staging", "postgresql+psycopg://u:p@db:5432/liman_salon", "1"),
        ("staging", "postgresql+psycopg://u:p@db:5432/liman_salon_staging_backup", "1"),
        ("staging", "", "1"),
    ],
    ids=[
        "empty-environment",
        "unknown-environment",
        "production-environment",
        "missing-allow-flag",
        "production-database",
        "similar-database-name",
        "empty-database-url",
    ],
)
def test_seed_refusal_never_opens_db_session(
    staging_seed, stubbed_seed_env, environment, database_url, allow
) -> None:
    calls, apply_env = stubbed_seed_env
    apply_env(environment=environment, database_url=database_url, allow=allow)

    with pytest.raises(SystemExit, match="Refusing staging demo seed"):
        staging_seed.seed()

    assert calls == []


def test_seed_opens_session_only_after_guards_pass(staging_seed, stubbed_seed_env) -> None:
    """Control: proves the stub is on the real code path, so the refusal test is not vacuous."""
    calls, apply_env = stubbed_seed_env
    apply_env(environment="staging", database_url=STAGING_URL, allow="1")

    with pytest.raises(_StubSessionLocalCalled):
        staging_seed.seed()

    assert len(calls) == 1


def test_public_booking_test_seed_still_refuses_staging_db(test_db_seed) -> None:
    """Regression: local test seed must not accept liman_salon_staging."""
    with pytest.raises(SystemExit, match="liman_salon_test"):
        test_db_seed._assert_test_database_url(
            "postgresql+psycopg://u:p@db:5432/liman_salon_staging"
        )


def test_seed_demo_catalog_idempotent_and_links_on_postgres(staging_seed) -> None:
    from app.core.config import get_settings
    from app.db.models.salon import Salon
    from app.db.models.service import Service
    from app.db.models.staff import Staff
    from app.db.models.staff_service import StaffService
    from app.db.models.user import User
    from app.db.models.working_hour import WorkingHour
    from app.db.session import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL test database not reachable")

    get_settings.cache_clear()
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        users_before = session.scalar(select(func.count()).select_from(User)) or 0

        salon1, action1 = staging_seed.seed_demo_catalog(session)
        assert action1 == "created"
        assert salon1.slug == staging_seed.SALON_SLUG
        assert salon1.name == staging_seed.SALON_NAME
        assert salon1.timezone == "Asia/Bishkek"
        assert salon1.currency_code == "KGS"

        staff_ids = {
            s.display_name: s.id
            for s in session.scalars(
                select(Staff).where(Staff.salon_id == salon1.id)
            ).all()
            if s.display_name in staging_seed.STAFF_NAMES
        }
        assert set(staff_ids) == set(staging_seed.STAFF_NAMES)

        service_ids = {
            s.name: s.id
            for s in session.scalars(
                select(Service).where(Service.salon_id == salon1.id)
            ).all()
            if s.name in {sp.name for sp in staging_seed.SERVICE_SPECS}
        }
        assert len(service_ids) == 4

        for staff_name, svc_names in staging_seed.STAFF_SERVICE_MAP.items():
            for svc_name in svc_names:
                link = session.scalar(
                    select(StaffService).where(
                        StaffService.staff_id == staff_ids[staff_name],
                        StaffService.service_id == service_ids[svc_name],
                    )
                )
                assert link is not None
                assert link.salon_id == salon1.id

        hours = list(
            session.scalars(
                select(WorkingHour).where(
                    WorkingHour.salon_id == salon1.id,
                    WorkingHour.staff_id.is_(None),
                )
            ).all()
        )
        assert {h.day_of_week for h in hours} == set(range(0, 6))
        assert all(h.start_time == time(10, 0) and h.end_time == time(19, 0) for h in hours)

        salon2, action2 = staging_seed.seed_demo_catalog(session)
        assert action2 == "reused"
        assert salon2.id == salon1.id

        staff_count = session.scalar(
            select(func.count())
            .select_from(Staff)
            .where(
                Staff.salon_id == salon1.id,
                Staff.display_name.in_(list(staging_seed.STAFF_NAMES)),
            )
        )
        service_count = session.scalar(
            select(func.count())
            .select_from(Service)
            .where(
                Service.salon_id == salon1.id,
                Service.name.in_([sp.name for sp in staging_seed.SERVICE_SPECS]),
            )
        )
        assert staff_count == 2
        assert service_count == 4

        # Does not create users; leaves other salons alone
        users_after = session.scalar(select(func.count()).select_from(User)) or 0
        assert users_after == users_before

        other = Salon(
            name="Other Tenant",
            slug=f"other-{salon1.id.hex[:8]}",
            timezone="UTC",
            currency_code="USD",
            is_active=True,
        )
        session.add(other)
        session.flush()
        staging_seed.seed_demo_catalog(session)
        still = session.get(Salon, other.id)
        assert still is not None and still.name == "Other Tenant"
    finally:
        session.close()
        transaction.rollback()
        connection.close()
