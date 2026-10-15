"""PostgreSQL transaction advisory locks for per-salon schedule gates."""

from __future__ import annotations

import hashlib
import uuid
from typing import Final

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.services.schedule.errors import ScheduleBusyError

_SCHEDULE_GATE_PREFIX: Final[bytes] = b"liman.schedule_gate.v1\x00"
_LOCK_TIMEOUT_MS: Final[str] = "2000"

_SET_LOCK_TIMEOUT = text("SELECT set_config('lock_timeout', :value, true)")
_ADVISORY_LOCK_SHARED = text("SELECT pg_advisory_xact_lock_shared(CAST(:key AS bigint))")
_ADVISORY_LOCK_EXCLUSIVE = text("SELECT pg_advisory_xact_lock(CAST(:key AS bigint))")


def salon_schedule_lock_key(salon_id: uuid.UUID) -> int:
    """Deterministic signed int64 advisory lock key for a salon."""
    digest = hashlib.sha256(_SCHEDULE_GATE_PREFIX + salon_id.bytes).digest()[:8]
    return int.from_bytes(digest, byteorder="big", signed=True)


def _lock_not_available(exc: OperationalError) -> bool:
    orig = exc.orig
    if orig is None:
        return False
    seen: set[int] = set()
    stack: list[BaseException] = [orig]
    while stack:
        current = stack.pop()
        node_id = id(current)
        if node_id in seen:
            continue
        seen.add(node_id)
        sqlstate = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        if sqlstate == "55P03":
            return True
        cause = getattr(current, "__cause__", None)
        if cause is not None:
            stack.append(cause)
        context = getattr(current, "__context__", None)
        if context is not None:
            stack.append(context)
    return False


def _set_lock_timeout_ms(session: Session) -> str:
    previous = session.execute(_SET_LOCK_TIMEOUT, {"value": _LOCK_TIMEOUT_MS}).scalar_one()
    return previous if previous is not None else "0"


def _restore_lock_timeout(session: Session, previous: str) -> None:
    session.execute(_SET_LOCK_TIMEOUT, {"value": previous})


def _acquire(session: Session, salon_id: uuid.UUID, *, shared: bool) -> None:
    key = salon_schedule_lock_key(salon_id)
    lock_stmt = _ADVISORY_LOCK_SHARED if shared else _ADVISORY_LOCK_EXCLUSIVE
    previous = _set_lock_timeout_ms(session)
    try:
        session.execute(lock_stmt, {"key": key})
    except OperationalError as exc:
        # Rollback aborts the whole transaction; acquire before any business writes.
        session.rollback()
        if _lock_not_available(exc):
            raise ScheduleBusyError("schedule gate busy") from exc
        raise
    else:
        _restore_lock_timeout(session, previous)


def acquire_schedule_lock_shared(session: Session, salon_id: uuid.UUID) -> None:
    """Acquire a shared transaction-level schedule gate lock for ``salon_id``."""
    _acquire(session, salon_id, shared=True)


def acquire_schedule_lock_exclusive(session: Session, salon_id: uuid.UUID) -> None:
    """Acquire an exclusive transaction-level schedule gate lock for ``salon_id``."""
    _acquire(session, salon_id, shared=False)
