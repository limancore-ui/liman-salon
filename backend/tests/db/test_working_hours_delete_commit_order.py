"""ASGI proof that working_hours.delete commits before HTTP 204 starts."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
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
WH_URL = f"/api/v1/salons/{SALON_A}/schedule/working-hours/{WH_ID}"

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


def _services(app: Any) -> None:
    schedule = MagicMock()
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


def test_delete_explicit_commit_precedes_http_204() -> None:
    events: list[str] = []
    statuses: list[int] = []
    db = _mock_session(lambda: events.append("db.commit"))
    app = create_app()
    app.add_middleware(ResponseStartRecordingMiddleware, events=events, statuses=statuses)
    headers = _auth(app)
    _services(app)

    with patch("app.db.session.SessionLocal", MagicMock(return_value=db)):
        with TestClient(app) as client:
            response = client.request("DELETE", WH_URL, headers=headers, json=_body())

    assert response.status_code == 204
    assert response.content == b""
    assert statuses == [204]
    first_commit = events.index("db.commit")
    response_start = events.index("http.response.start")
    trailing_commit = events.index("db.commit", first_commit + 1)
    assert first_commit < response_start < trailing_commit, events


def test_delete_explicit_commit_failure_does_not_return_204() -> None:
    events: list[str] = []
    statuses: list[int] = []

    def _commit() -> None:
        events.append("db.commit_failed")
        raise SQLAlchemyError("simulated commit failure")

    db = _mock_session(_commit)
    app = create_app()
    app.add_middleware(ResponseStartRecordingMiddleware, events=events, statuses=statuses)
    headers = _auth(app)
    _services(app)

    with patch("app.db.session.SessionLocal", MagicMock(return_value=db)):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.request("DELETE", WH_URL, headers=headers, json=_body())

    assert response.status_code != 204
    assert response.status_code == 500
    assert 204 not in statuses
    assert events.index("db.commit_failed") < events.index("http.response.start"), events
    db.rollback.assert_called()
