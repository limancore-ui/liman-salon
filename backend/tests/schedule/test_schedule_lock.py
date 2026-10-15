"""Unit and PostgreSQL tests for schedule advisory lock helpers."""

from __future__ import annotations

import threading
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.services.schedule.errors import ScheduleBusyError
from app.services.schedule.lock import (
    _ADVISORY_LOCK_EXCLUSIVE,
    _ADVISORY_LOCK_SHARED,
    _SET_LOCK_TIMEOUT,
    acquire_schedule_lock_exclusive,
    acquire_schedule_lock_shared,
    salon_schedule_lock_key,
)

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SALON_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def test_salon_schedule_lock_key_is_deterministic() -> None:
    assert salon_schedule_lock_key(SALON_A) == salon_schedule_lock_key(SALON_A)


def test_salon_schedule_lock_key_within_signed_int64_range() -> None:
    for salon_id in (SALON_A, SALON_B, uuid.uuid4(), uuid.UUID(int=0)):
        key = salon_schedule_lock_key(salon_id)
        assert INT64_MIN <= key <= INT64_MAX


def test_salon_schedule_lock_key_differs_across_salons() -> None:
    assert salon_schedule_lock_key(SALON_A) != salon_schedule_lock_key(SALON_B)


def test_acquire_shared_executes_set_config_and_shared_lock() -> None:
    session = MagicMock()
    set_config_result = MagicMock()
    set_config_result.scalar_one.return_value = "0"
    session.execute.side_effect = [set_config_result, None, None]

    acquire_schedule_lock_shared(session, SALON_A)

    key = salon_schedule_lock_key(SALON_A)
    assert session.execute.call_args_list == [
        call(_SET_LOCK_TIMEOUT, {"value": "2000"}),
        call(_ADVISORY_LOCK_SHARED, {"key": key}),
        call(_SET_LOCK_TIMEOUT, {"value": "0"}),
    ]


def test_acquire_exclusive_executes_exclusive_lock() -> None:
    session = MagicMock()
    set_config_result = MagicMock()
    set_config_result.scalar_one.return_value = "1s"
    session.execute.side_effect = [set_config_result, None, None]

    acquire_schedule_lock_exclusive(session, SALON_A)

    key = salon_schedule_lock_key(SALON_A)
    assert session.execute.call_args_list[1] == call(_ADVISORY_LOCK_EXCLUSIVE, {"key": key})
    assert session.execute.call_args_list[2] == call(_SET_LOCK_TIMEOUT, {"value": "1s"})


def test_operational_error_55p03_maps_to_schedule_busy_and_rollbacks() -> None:
    session = MagicMock()
    set_config_result = MagicMock()
    set_config_result.scalar_one.return_value = "0"
    orig = SimpleNamespace(sqlstate="55P03")
    session.execute.side_effect = [
        set_config_result,
        OperationalError("SELECT pg_advisory_xact_lock", {}, orig),
    ]

    with pytest.raises(ScheduleBusyError, match="schedule gate busy"):
        acquire_schedule_lock_exclusive(session, SALON_A)

    session.rollback.assert_called_once()


def test_operational_error_55p03_on_cause_maps_to_schedule_busy_and_rollbacks() -> None:
    session = MagicMock()
    set_config_result = MagicMock()
    set_config_result.scalar_one.return_value = "0"
    orig = SimpleNamespace()
    orig.__cause__ = SimpleNamespace(sqlstate="55P03")
    session.execute.side_effect = [
        set_config_result,
        OperationalError("SELECT pg_advisory_xact_lock", {}, orig),
    ]

    with pytest.raises(ScheduleBusyError, match="schedule gate busy"):
        acquire_schedule_lock_exclusive(session, SALON_A)

    session.rollback.assert_called_once()


def test_operational_error_other_sqlstate_reraises_and_rollbacks() -> None:
    session = MagicMock()
    set_config_result = MagicMock()
    set_config_result.scalar_one.return_value = "0"
    orig = SimpleNamespace(sqlstate="57014")
    lock_error = OperationalError("SELECT pg_advisory_xact_lock", {}, orig)
    session.execute.side_effect = [set_config_result, lock_error]

    with pytest.raises(OperationalError) as raised:
        acquire_schedule_lock_shared(session, SALON_A)

    assert raised.value is lock_error
    session.rollback.assert_called_once()


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


_pg_only = pytest.mark.skipif(
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


@_pg_only
def test_postgres_shared_lock_acquires_within_transaction(db_session: Session) -> None:
    acquire_schedule_lock_shared(db_session, SALON_A)
    key = salon_schedule_lock_key(SALON_A)
    held = db_session.execute(
        text("SELECT pg_try_advisory_xact_lock_shared(CAST(:key AS bigint))"),
        {"key": key},
    ).scalar_one()
    assert held is True


@_pg_only
def test_postgres_exclusive_blocks_second_exclusive_until_rollback() -> None:
    holder_ready = threading.Event()
    waiter_finished = threading.Event()
    results: dict[str, str] = {}

    def holder() -> None:
        session = SessionLocal()
        try:
            acquire_schedule_lock_exclusive(session, SALON_A)
            holder_ready.set()
            waiter_finished.wait(timeout=10)
            session.rollback()
            results["holder"] = "ok"
        finally:
            session.close()

    def waiter() -> None:
        assert holder_ready.wait(timeout=10)
        session = SessionLocal()
        try:
            with pytest.raises(ScheduleBusyError):
                acquire_schedule_lock_exclusive(session, SALON_A)
            assert session.execute(text("SELECT 1")).scalar_one() == 1
            results["waiter"] = "busy"
            session.rollback()
        finally:
            session.close()
            waiter_finished.set()

    t_holder = threading.Thread(target=holder)
    t_waiter = threading.Thread(target=waiter)
    t_holder.start()
    t_waiter.start()
    t_holder.join(timeout=15)
    t_waiter.join(timeout=15)

    assert not t_holder.is_alive() and not t_waiter.is_alive()
    assert results == {"holder": "ok", "waiter": "busy"}
