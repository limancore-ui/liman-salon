from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_as_of, get_smart_gap_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.availability.types import TimeInterval
from app.services.smart_gap.service import SmartGapService
from app.services.smart_gap.types import SmartGapEntry, SmartGapResult, SuitableService

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STAFF_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
SERVICE_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
NOW = datetime.now(timezone.utc)
FIXED_AS_OF = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
START_DATE = date(2026, 9, 25)
END_DATE = date(2026, 9, 26)

GAP_START = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
GAP_END = datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc)


def _smart_gap_result() -> SmartGapResult:
    return SmartGapResult(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        entries=(
            SmartGapEntry(
                gap=TimeInterval(start=GAP_START, end=GAP_END),
                suitable_services=(
                    SuitableService(
                        service_id=SERVICE_ID,
                        name="Haircut",
                        duration_minutes=60,
                        price_cents=2500,
                    ),
                ),
            ),
        ),
    )


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
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
    mock_smart_gap = MagicMock(spec=SmartGapService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_smart_gap_service] = lambda: mock_smart_gap
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_smart_gap, headers


def _url(salon_id: uuid.UUID = SALON_A) -> str:
    return (
        f"/api/v1/salons/{salon_id}/smart-gaps"
        f"?staff_id={STAFF_ID}"
        f"&start_date={START_DATE.isoformat()}"
        f"&end_date={END_DATE.isoformat()}"
    )


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_smart_gaps_read_roles(role: str) -> None:
    client, mock_smart_gap, headers = _auth_app(role=role)
    mock_smart_gap.get_gaps_with_suitable_services.return_value = _smart_gap_result()
    response = client.get(_url(), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["salon_id"] == str(SALON_A)
    assert body["staff_id"] == str(STAFF_ID)
    assert len(body["gaps"]) == 1
    assert body["gaps"][0]["start"] == GAP_START.isoformat().replace("+00:00", "Z")
    assert body["gaps"][0]["end"] == GAP_END.isoformat().replace("+00:00", "Z")
    svc = body["gaps"][0]["suitable_services"][0]
    assert svc["service_id"] == str(SERVICE_ID)
    assert svc["name"] == "Haircut"
    assert svc["duration_minutes"] == 60
    assert svc["price_cents"] == 2500
    mock_smart_gap.get_gaps_with_suitable_services.assert_called_once_with(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
        start_date=START_DATE,
        end_date=END_DATE,
        as_of=FIXED_AS_OF,
    )
    client.close()


def test_list_smart_gaps_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(_url()).status_code == 401


def test_list_smart_gaps_no_membership_403() -> None:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="o@e.com",
        full_name="O",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_A,
        name="S",
        slug="s",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_smart_gap_service] = lambda: MagicMock(spec=SmartGapService)
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        r = client.get(_url(), headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["code"] == "salon_access_denied"


def test_list_smart_gaps_cross_tenant_403() -> None:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B,
        name="Other Salon",
        slug="other",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    mock_smart_gap = MagicMock(spec=SmartGapService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_smart_gap_service] = lambda: mock_smart_gap
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        response = client.get(
            _url(salon_id=SALON_B),
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    mock_smart_gap.get_gaps_with_suitable_services.assert_not_called()
