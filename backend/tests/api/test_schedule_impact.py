from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_schedule_impact_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.schedule.impact import ImpactBookingRow, ImpactPreviewResult, ScheduleImpactService

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STAFF_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
BOOKING_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
SERVICE_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime.now(timezone.utc)

PREVIEW_URL = f"/api/v1/salons/{SALON_A}/schedule/impact-preview"


def _preview_result(*, total: int = 1, offset: int = 0, limit: int = 50) -> ImpactPreviewResult:
    row = ImpactBookingRow(
        booking_id=BOOKING_ID,
        status="confirmed",
        is_in_progress=False,
        starts_at=NOW + timedelta(days=2),
        ends_at=NOW + timedelta(days=2, hours=1),
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        customer_name="Client",
        service_name="Cut",
        reasons=("outside_availability",),
    )
    all_rows = tuple([row] * total)
    page = all_rows[offset : offset + limit]
    return ImpactPreviewResult(
        as_of=NOW,
        change_kind="working_hours.update",
        affected_staff_ids=(STAFF_ID,),
        starts_at_from=NOW,
        starts_at_to=NOW + timedelta(days=90),
        horizon_days=90,
        impacts=page,
        all_impacts=all_rows,
        impact_fingerprint="a" * 64,
        schedule_refs=(),
        impact_offset=offset,
        impact_limit=limit,
    )


def _auth_app(
    *, role: str = "owner", salon_id: uuid.UUID = SALON_A
) -> tuple[TestClient, MagicMock, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon_id,
        name="Salon",
        slug="salon",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    mock_impact = MagicMock(spec=ScheduleImpactService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_schedule_impact_service] = lambda: mock_impact
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_impact, headers


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_impact_preview_allowed_for_write_roles(role: str) -> None:
    client, mock_impact, headers = _auth_app(role=role)
    mock_impact.preview_impact.return_value = _preview_result()
    body = {
        "change": {
            "kind": "working_hours.delete",
            "working_hours_id": str(uuid.uuid4()),
        }
    }
    response = client.post(PREVIEW_URL, json=body, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["impact_fingerprint"] == "a" * 64
    assert payload["counts"]["total_impacted"] == 1
    assert payload["pagination"]["has_more"] is False
    mock_impact.preview_impact.assert_called_once()
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_impact_preview_denied_for_read_roles(role: str) -> None:
    client, mock_impact, headers = _auth_app(role=role)
    body = {
        "change": {
            "kind": "staff_service.detach",
            "staff_id": str(STAFF_ID),
            "service_id": str(SERVICE_ID),
        }
    }
    response = client.post(PREVIEW_URL, json=body, headers=headers)
    assert response.status_code == 403
    mock_impact.preview_impact.assert_not_called()
    client.close()


def test_impact_preview_cross_tenant_path_mismatch() -> None:
    client, mock_impact, headers = _auth_app(salon_id=SALON_B)
    body = {
        "change": {
            "kind": "working_hours.delete",
            "working_hours_id": str(uuid.uuid4()),
        }
    }
    response = client.post(PREVIEW_URL, json=body, headers=headers)
    assert response.status_code == 500
    mock_impact.preview_impact.assert_not_called()
    client.close()


def test_impact_preview_has_more_and_full_counts() -> None:
    client, mock_impact, headers = _auth_app()
    mock_impact.preview_impact.return_value = _preview_result(total=3, offset=0, limit=2)
    body = {
        "change": {
            "kind": "blocked_period.create",
            "staff_id": str(STAFF_ID),
            "starts_at": "2026-08-01T09:00:00+00:00",
            "ends_at": "2026-08-01T12:00:00+00:00",
            "block_type": "manual",
        },
        "impact_limit": 2,
    }
    response = client.post(PREVIEW_URL, json=body, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["counts"]["total_impacted"] == 3
    assert payload["pagination"]["returned"] == 2
    assert payload["pagination"]["has_more"] is True
    client.close()


def test_impact_preview_does_not_mutate_via_service() -> None:
    client, mock_impact, headers = _auth_app()
    mock_impact.preview_impact.return_value = _preview_result(total=0)
    body = {
        "change": {
            "kind": "staff_service.detach",
            "staff_id": str(STAFF_ID),
            "service_id": str(SERVICE_ID),
        }
    }
    response = client.post(PREVIEW_URL, json=body, headers=headers)
    assert response.status_code == 200
    mock_impact.preview_impact.assert_called_once()
    assert "session" not in str(mock_impact.method_calls)
    client.close()
