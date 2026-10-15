"""ASGI proof that working_hours.create commits before HTTP 201 starts.

The global get_db characterization lives in test_get_db_asgi_response_commit_order.py
and is left unchanged. This sibling exercises the real create route.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_clock, get_schedule_impact_service, get_schedule_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WH_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
TOKEN_NOW = datetime.now(timezone.utc)
FINGERPRINT = "d" * 64
WH_URL = f"/api/v1/salons/{SALON_A}/schedule/working-hours"

Send = Callable[[dict[str, Any]], Awaitable[None]]


class ResponseStartRecordingMiddleware:
    def __init__(self, app: Any, events: list[str], statuses: list[int]) -> None:
        self.app = app
        self.events = events
        self.statuses = statuses

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                status = message.get("status")
                if isinstance(status, int):
                    self.statuses.append(status)
                self.events.append("http.response.start")
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _auth(app: Any) -> dict[str, str]:
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_A,
        name="Salon",
        slug="salon",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=SALON_A,
        user_id=USER_ID,
        role="owner",
        is_active=True,
    )
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=TOKEN_NOW)
    return {"Authorization": f"Bearer {token}"}


def _services(app: Any, row: SimpleNamespace) -> None:
    schedule = MagicMock()
    schedule.create_working_hour.return_value = row
    impact = MagicMock()
    impact.preview_impact.return_value = SimpleNamespace(
        impact_fingerprint=FINGERPRINT,
        all_impacts=(),
    )
    app.dependency_overrides[get_schedule_service] = lambda: schedule
    app.dependency_overrides[get_schedule_impact_service] = lambda: impact
    app.dependency_overrides[get_clock] = lambda: (lambda: NOW)


def _body() -> dict[str, object]:
    return {
        "day_of_week": 1,
        "start_time": "09:00:00",
        "end_time": "17:00:00",
        "impact_fingerprint": FINGERPRINT,
        "as_of": NOW.isoformat(),
        "horizon_days": 90,
        "acknowledge_impacts": False,
    }


def _mock_session(commit: Callable[[], None]) -> MagicMock:
    db = MagicMock()
    lock_result = MagicMock()
    lock_result.scalar_one.return_value = "0"
    db.execute.return_value = lock_result
    db.commit.side_effect = commit
    db.rollback = MagicMock()
    db.close = MagicMock()
    return db


def test_create_explicit_commit_precedes_http_201() -> None:
    events: list[str] = []
    statuses: list[int] = []
    row = SimpleNamespace(
        id=WH_ID,
        salon_id=SALON_A,
        staff_id=None,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
        effective_from=None,
        effective_to=None,
        created_at=NOW,
        updated_at=NOW,
    )

    def _commit() -> None:
        events.append("db.commit")
        # If the response model were built after commit, these writes would leak into it.
        row.id = None
        row.created_at = None
        row.updated_at = None

    db = _mock_session(_commit)
    app = create_app()
    app.add_middleware(ResponseStartRecordingMiddleware, events=events, statuses=statuses)
    headers = _auth(app)
    _services(app, row)

    with patch("app.db.session.SessionLocal", MagicMock(return_value=db)):
        with TestClient(app) as client:
            response = client.post(WH_URL, headers=headers, json=_body())

    assert response.status_code == 201
    assert response.json()["id"] == str(WH_ID)
    assert response.json()["created_at"] is not None
    assert statuses == [201]
    first_commit = events.index("db.commit")
    response_start = events.index("http.response.start")
    trailing_commit = events.index("db.commit", first_commit + 1)
    assert first_commit < response_start < trailing_commit, events


def test_create_explicit_commit_failure_does_not_return_201() -> None:
    events: list[str] = []
    statuses: list[int] = []

    def _commit() -> None:
        events.append("db.commit_failed")
        raise SQLAlchemyError("simulated commit failure")

    row = SimpleNamespace(
        id=WH_ID,
        salon_id=SALON_A,
        staff_id=None,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
        effective_from=None,
        effective_to=None,
        created_at=NOW,
        updated_at=NOW,
    )
    db = _mock_session(_commit)
    app = create_app()
    app.add_middleware(ResponseStartRecordingMiddleware, events=events, statuses=statuses)
    headers = _auth(app)
    _services(app, row)

    with patch("app.db.session.SessionLocal", MagicMock(return_value=db)):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(WH_URL, headers=headers, json=_body())

    assert response.status_code != 201
    assert response.status_code == 500
    assert 201 not in statuses
    assert events.index("db.commit_failed") < events.index("http.response.start"), events
    db.rollback.assert_called()
