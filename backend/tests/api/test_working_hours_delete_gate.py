"""HTTP commit gate for working_hours.delete (freshness, fingerprint, acknowledgement)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.deps import (
    get_clock,
    get_db,
    get_schedule_impact_service,
    get_schedule_service,
)
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.schedule.errors import ScheduleNotFoundError
from app.services.schedule.service import ScheduleService

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
WH_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
TOKEN_NOW = datetime.now(timezone.utc)
FINGERPRINT = "ab" * 32
WH_URL = f"/api/v1/salons/{SALON_A}/schedule/working-hours/{WH_ID}"


def _body(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "impact_fingerprint": FINGERPRINT,
        "as_of": NOW.isoformat(),
        "horizon_days": 30,
        "acknowledge_impacts": False,
    }
    payload.update(overrides)
    return payload


def _app(
    *,
    fingerprint: str = FINGERPRINT,
    impacts: tuple[object, ...] = (),
    execute_side_effect: object | None = None,
) -> tuple[TestClient, MagicMock, MagicMock, MagicMock]:
    app = create_app()
    db = MagicMock()
    if execute_side_effect is None:
        lock_result = MagicMock()
        lock_result.scalar_one.return_value = "0"
        db.execute.return_value = lock_result
    else:
        db.execute.side_effect = execute_side_effect

    def override_get_db():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

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
    schedule = MagicMock(spec=ScheduleService)
    impact = MagicMock()
    impact.preview_impact.return_value = SimpleNamespace(
        impact_fingerprint=fingerprint,
        all_impacts=impacts,
    )
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_schedule_service] = lambda: schedule
    app.dependency_overrides[get_schedule_impact_service] = lambda: impact
    app.dependency_overrides[get_clock] = lambda: (lambda: NOW)
    token, _ = create_access_token(user_id=USER_ID, now=TOKEN_NOW)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, schedule, impact, db


def test_valid_preview_deletes_and_commits() -> None:
    client, schedule, impact, db = _app()
    response = client.request("DELETE", WH_URL, json=_body())
    assert response.status_code == 204
    assert response.content == b""
    schedule.delete_working_hour.assert_called_once()
    kwargs = impact.preview_impact.call_args.kwargs
    assert kwargs["as_of"] == NOW
    assert kwargs["as_of"].tzinfo == timezone.utc
    assert kwargs["horizon_days"] == 30
    assert kwargs["change"].working_hours_id == WH_ID
    assert kwargs["change"].kind == "working_hours.delete"
    assert db.commit.call_count == 2
    client.close()


def test_equivalent_offset_is_normalized_to_utc_before_recompute() -> None:
    client, _schedule, impact, _db = _app()
    echoed = (NOW + timedelta(hours=5)).replace(tzinfo=timezone(timedelta(hours=5)))
    response = client.request("DELETE", WH_URL, json=_body(as_of=echoed.isoformat()))
    assert response.status_code == 204
    assert impact.preview_impact.call_args.kwargs["as_of"] == NOW
    client.close()


@pytest.mark.parametrize(
    "missing",
    ["impact_fingerprint", "as_of", "horizon_days", "acknowledge_impacts"],
)
def test_missing_gate_fields_rejected(missing: str) -> None:
    client, schedule, impact, db = _app()
    payload = _body()
    del payload[missing]
    response = client.request("DELETE", WH_URL, json=payload)
    assert response.status_code == 422
    schedule.delete_working_hour.assert_not_called()
    impact.preview_impact.assert_not_called()
    db.execute.assert_not_called()
    db.commit.assert_not_called()
    client.close()


def test_unknown_gate_fields_rejected() -> None:
    client, schedule, impact, db = _app()
    response = client.request("DELETE", WH_URL, json=_body(impact_offset=10, working_hours_id=str(WH_ID)))
    assert response.status_code == 422
    schedule.delete_working_hour.assert_not_called()
    impact.preview_impact.assert_not_called()
    db.execute.assert_not_called()
    client.close()


def test_naive_as_of_returns_validation_error() -> None:
    client, schedule, impact, db = _app()
    response = client.request("DELETE", WH_URL, json=_body(as_of="2026-09-24T12:00:00"))
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    schedule.delete_working_hour.assert_not_called()
    impact.preview_impact.assert_not_called()
    db.execute.assert_not_called()
    client.close()


def test_malformed_as_of_rejected() -> None:
    client, schedule, impact, db = _app()
    response = client.request("DELETE", WH_URL, json=_body(as_of="not-a-timestamp"))
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    schedule.delete_working_hour.assert_not_called()
    impact.preview_impact.assert_not_called()
    db.execute.assert_not_called()
    client.close()


@pytest.mark.parametrize(
    ("delta", "status", "code"),
    [
        (timedelta(seconds=5), 204, None),
        (timedelta(seconds=5, microseconds=1), 422, "validation_error"),
    ],
)
def test_future_skew_boundary(delta: timedelta, status: int, code: str | None) -> None:
    client, schedule, impact, db = _app()
    response = client.request("DELETE", WH_URL, json=_body(as_of=(NOW + delta).isoformat()))
    assert response.status_code == status
    if code is None:
        assert schedule.delete_working_hour.call_count == 1
        assert response.content == b""
    else:
        assert response.json()["code"] == code
        schedule.delete_working_hour.assert_not_called()
        impact.preview_impact.assert_not_called()
        db.execute.assert_not_called()
    client.close()


@pytest.mark.parametrize(
    ("delta", "status", "code"),
    [
        (timedelta(seconds=900), 204, None),
        (timedelta(seconds=900, microseconds=1), 409, "impact_preview_expired"),
    ],
)
def test_preview_age_boundary(delta: timedelta, status: int, code: str | None) -> None:
    client, schedule, impact, db = _app()
    response = client.request("DELETE", WH_URL, json=_body(as_of=(NOW - delta).isoformat()))
    assert response.status_code == status
    if code is None:
        schedule.delete_working_hour.assert_called_once()
    else:
        assert response.json()["code"] == code
        schedule.delete_working_hour.assert_not_called()
        impact.preview_impact.assert_not_called()
        db.execute.assert_not_called()
        db.commit.assert_not_called()
    client.close()


def test_fingerprint_mismatch_is_stale_and_deletes_nothing() -> None:
    client, schedule, impact, db = _app(fingerprint="c" * 64)
    response = client.request("DELETE", WH_URL, json=_body())
    assert response.status_code == 409
    assert response.json()["code"] == "impact_stale"
    schedule.delete_working_hour.assert_not_called()
    impact.preview_impact.assert_called_once()
    db.commit.assert_not_called()
    client.close()


def test_impacts_without_acknowledgement_delete_nothing() -> None:
    client, schedule, _impact, db = _app(impacts=(object(),))
    response = client.request("DELETE", WH_URL, json=_body(acknowledge_impacts=False))
    assert response.status_code == 409
    assert response.json()["code"] == "impact_ack_required"
    schedule.delete_working_hour.assert_not_called()
    db.commit.assert_not_called()
    client.close()


def test_impacts_with_acknowledgement_succeed() -> None:
    client, schedule, _impact, db = _app(impacts=(object(),))
    response = client.request("DELETE", WH_URL, json=_body(acknowledge_impacts=True))
    assert response.status_code == 204
    assert response.content == b""
    schedule.delete_working_hour.assert_called_once()
    assert db.commit.call_count == 2
    client.close()


def test_zero_impacts_without_acknowledgement_succeed() -> None:
    client, schedule, _impact, _db = _app(impacts=())
    response = client.request("DELETE", WH_URL, json=_body(acknowledge_impacts=False))
    assert response.status_code == 204
    schedule.delete_working_hour.assert_called_once()
    client.close()


def test_missing_row_returns_404_without_delete() -> None:
    client, schedule, impact, db = _app()
    impact.preview_impact.side_effect = ScheduleNotFoundError("working hours not found")
    response = client.request("DELETE", WH_URL, json=_body())
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    schedule.delete_working_hour.assert_not_called()
    db.commit.assert_not_called()
    client.close()


def test_lock_timeout_returns_schedule_busy_and_deletes_nothing() -> None:
    lock_result = MagicMock()
    lock_result.scalar_one.return_value = "0"
    orig = SimpleNamespace(sqlstate="55P03")
    client, schedule, impact, db = _app(
        execute_side_effect=[
            lock_result,
            OperationalError("SELECT pg_advisory_xact_lock", {}, orig),
        ]
    )
    response = client.request("DELETE", WH_URL, json=_body())
    assert response.status_code == 503
    assert response.headers.get("retry-after") == "2"
    assert response.json()["code"] == "schedule_busy"
    schedule.delete_working_hour.assert_not_called()
    impact.preview_impact.assert_not_called()
    db.commit.assert_not_called()
    client.close()
