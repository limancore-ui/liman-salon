"""ASGI-level characterization: HTTP response vs get_db commit ordering.

Uses a minimal FastAPI app with the real ``get_db`` dependency (not the generator
in isolation). SessionLocal is patched so no production database is required.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db

Event = str
Send = Callable[[dict[str, Any]], Awaitable[None]]


class ResponseStartRecordingMiddleware:
    """Record ``http.response.start`` as seen at the ASGI server boundary."""

    def __init__(self, app: Any, events: list[Event]) -> None:
        self.app = app
        self.events = events

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                self.events.append("http.response.start")
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _build_probe_app(events: list[Event]) -> FastAPI:
    app = FastAPI()

    @app.get("/probe")
    def probe(db: Session = Depends(get_db)) -> dict[str, str]:
        assert db is not None
        events.append("handler_complete")
        return {"status": "ok"}

    app.add_middleware(ResponseStartRecordingMiddleware, events=events)
    return app


def _mock_session_factory(events: list[Event]) -> MagicMock:
    mock_db = MagicMock(spec=Session)

    def _commit() -> None:
        events.append("db.commit")

    mock_db.commit.side_effect = _commit
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()
    return mock_db


def test_asgi_success_records_handler_response_start_and_commit_order() -> None:
    events: list[Event] = []
    mock_db = _mock_session_factory(events)
    session_local = MagicMock(return_value=mock_db)

    app = _build_probe_app(events)

    with patch("app.db.session.SessionLocal", session_local):
        with TestClient(app) as client:
            response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    assert "handler_complete" in events
    assert "http.response.start" in events
    assert "db.commit" in events

    handler_idx = events.index("handler_complete")
    response_start_idx = events.index("http.response.start")
    commit_idx = events.index("db.commit")

    # Characterization: document observable ASGI ordering (not get_db alone).
    observed_order = events.copy()
    assert handler_idx < commit_idx, (
        "handler must finish before get_db teardown commit; events=%r" % observed_order
    )
    assert handler_idx < response_start_idx, (
        "handler must finish before response starts; events=%r" % observed_order
    )
    # Key PR-1 question: can the client see HTTP 200 before commit runs?
    assert response_start_idx < commit_idx, (
        "expected http.response.start before db.commit (response may precede commit); "
        "events=%r" % observed_order
    )
    mock_db.close.assert_called_once()


def test_asgi_commit_failure_observed_http_outcome_and_order() -> None:
    """When commit fails in get_db teardown, record what the client actually saw."""
    events: list[Event] = []
    mock_db = MagicMock(spec=Session)

    def _commit_fail() -> None:
        events.append("db.commit_failed")
        raise SQLAlchemyError("simulated commit failure")

    mock_db.commit.side_effect = _commit_fail
    mock_db.rollback = MagicMock()
    mock_db.close = MagicMock()
    session_local = MagicMock(return_value=mock_db)

    app = _build_probe_app(events)

    with patch("app.db.session.SessionLocal", session_local):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/probe")

    assert "handler_complete" in events
    assert "http.response.start" in events
    assert "db.commit_failed" in events

    handler_idx = events.index("handler_complete")
    response_start_idx = events.index("http.response.start")
    commit_fail_idx = events.index("db.commit_failed")

    assert handler_idx < response_start_idx < commit_fail_idx, (
        "commit fails only after ASGI response.start; events=%r" % events
    )

    assert "db.commit" not in events
    # Characterization: HTTP success-shaped response despite commit failure (unsafe).
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # Test records rollback separately — must not infer DB success from HTTP 200 alone.
    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()
