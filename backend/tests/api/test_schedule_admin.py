from __future__ import annotations

import uuid
from datetime import datetime, time, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_schedule_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.schedule.errors import ScheduleNotFoundError, ScheduleValidationError
from app.services.schedule.service import (
    BlockedPeriodCreateData,
    ScheduleService,
    WorkingHoursCreateData,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STAFF_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
WH_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
BP_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime.now(timezone.utc)


def _working_hour_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": WH_ID,
        "salon_id": SALON_A,
        "staff_id": None,
        "day_of_week": 0,
        "start_time": time(9, 0),
        "end_time": time(17, 0),
        "effective_from": None,
        "effective_to": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _blocked_period_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": BP_ID,
        "salon_id": SALON_A,
        "staff_id": None,
        "starts_at": datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        "reason": "Closed",
        "block_type": "manual",
        "created_by_user_id": USER_ID,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


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
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    mock_schedule = MagicMock(spec=ScheduleService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_schedule_service] = lambda: mock_schedule
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_schedule, headers


WH_BASE = f"/api/v1/salons/{SALON_A}/schedule/working-hours"
BP_BASE = f"/api/v1/salons/{SALON_A}/schedule/blocked-periods"


# --- Working hours READ ---


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_working_hours_read_roles(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    mock_schedule.list_working_hours.return_value = [
        _working_hour_row(),
        _working_hour_row(id=uuid.uuid4(), staff_id=STAFF_ID),
    ]
    response = client.get(WH_BASE, headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
    mock_schedule.list_working_hours.assert_called_once_with(
        salon_id=SALON_A,
        staff_id=None,
    )
    client.close()


def test_list_working_hours_staff_filter() -> None:
    client, mock_schedule, headers = _auth_app()
    mock_schedule.list_working_hours.return_value = [_working_hour_row(staff_id=STAFF_ID)]
    response = client.get(f"{WH_BASE}?staff_id={STAFF_ID}", headers=headers)
    assert response.status_code == 200
    mock_schedule.list_working_hours.assert_called_once_with(
        salon_id=SALON_A,
        staff_id=STAFF_ID,
    )
    client.close()


def test_list_working_hours_ordering_preserved() -> None:
    client, mock_schedule, headers = _auth_app()
    mock_schedule.list_working_hours.return_value = [
        _working_hour_row(staff_id=None, day_of_week=0),
        _working_hour_row(id=uuid.uuid4(), staff_id=STAFF_ID, day_of_week=1),
    ]
    response = client.get(WH_BASE, headers=headers)
    body = response.json()
    assert body[0]["staff_id"] is None
    assert body[1]["staff_id"] == str(STAFF_ID)
    client.close()


def test_list_working_hours_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(WH_BASE).status_code == 401


def test_list_working_hours_no_membership_403() -> None:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID, email="o@e.com", full_name="O", is_active=True
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_A, name="S", slug="s", is_active=True
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_schedule_service] = lambda: MagicMock(spec=ScheduleService)
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        r = client.get(WH_BASE, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["code"] == "salon_access_denied"


def test_get_working_hours_detail_tenant_scoped() -> None:
    client, mock_schedule, headers = _auth_app()
    mock_schedule.get_working_hour.return_value = _working_hour_row()
    response = client.get(f"{WH_BASE}/{WH_ID}", headers=headers)
    assert response.status_code == 200
    mock_schedule.get_working_hour.assert_called_once_with(
        salon_id=SALON_A,
        working_hours_id=WH_ID,
    )
    client.close()


def test_get_working_hours_not_found() -> None:
    client, mock_schedule, headers = _auth_app()
    mock_schedule.get_working_hour.side_effect = ScheduleNotFoundError("working hours not found")
    assert client.get(f"{WH_BASE}/{WH_ID}", headers=headers).status_code == 404
    client.close()


def test_get_working_hours_cross_tenant_404() -> None:
    client, mock_schedule, headers = _auth_app(salon_id=SALON_A)
    mock_schedule.get_working_hour.side_effect = ScheduleNotFoundError("working hours not found")
    client.get(f"{WH_BASE}/{uuid.uuid4()}", headers=headers)
    assert mock_schedule.get_working_hour.call_args.kwargs["salon_id"] == SALON_A
    client.close()


# --- Working hours CREATE ---


def test_owner_create_salon_default_working_hours() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.create_working_hour.return_value = _working_hour_row()
    response = client.post(
        WH_BASE,
        headers=headers,
        json={
            "day_of_week": 1,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
    )
    assert response.status_code == 201
    assert mock_schedule.create_working_hour.call_args.kwargs["salon_id"] == SALON_A
    data = mock_schedule.create_working_hour.call_args.kwargs["data"]
    assert data.staff_id is None
    client.close()


def test_admin_create_staff_specific_working_hours() -> None:
    client, mock_schedule, headers = _auth_app(role="admin")
    mock_schedule.create_working_hour.return_value = _working_hour_row(staff_id=STAFF_ID)
    response = client.post(
        WH_BASE,
        headers=headers,
        json={
            "staff_id": str(STAFF_ID),
            "day_of_week": 2,
            "start_time": "10:00:00",
            "end_time": "18:00:00",
        },
    )
    assert response.status_code == 201
    assert mock_schedule.create_working_hour.call_args.kwargs["data"].staff_id == STAFF_ID
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_create_working_hours_forbidden(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    response = client.post(
        WH_BASE,
        headers=headers,
        json={"day_of_week": 0, "start_time": "09:00:00", "end_time": "17:00:00"},
    )
    assert response.status_code == 403
    mock_schedule.create_working_hour.assert_not_called()
    client.close()


def test_create_working_hours_body_cannot_override_salon_id() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.create_working_hour.return_value = _working_hour_row()
    response = client.post(
        WH_BASE,
        headers=headers,
        json={
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "salon_id": str(SALON_B),
        },
    )
    assert response.status_code == 422
    mock_schedule.create_working_hour.assert_not_called()
    client.close()


def test_create_working_hours_invalid_day_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        WH_BASE,
        headers=headers,
        json={"day_of_week": 7, "start_time": "09:00:00", "end_time": "17:00:00"},
    )
    assert response.status_code == 422
    client.close()


def test_create_working_hours_start_not_before_end_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        WH_BASE,
        headers=headers,
        json={"day_of_week": 0, "start_time": "17:00:00", "end_time": "09:00:00"},
    )
    assert response.status_code == 422
    client.close()


def test_create_working_hours_invalid_effective_range_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        WH_BASE,
        headers=headers,
        json={
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "effective_from": "2026-06-01",
            "effective_to": "2026-01-01",
        },
    )
    assert response.status_code == 422
    client.close()


def test_create_working_hours_cross_tenant_staff_404() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.create_working_hour.side_effect = ScheduleNotFoundError("staff not found")
    response = client.post(
        WH_BASE,
        headers=headers,
        json={
            "staff_id": str(uuid.uuid4()),
            "day_of_week": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
    )
    assert response.status_code == 404
    client.close()


def test_create_multiple_windows_same_weekday_allowed() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.create_working_hour.return_value = _working_hour_row()
    payload = {"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"}
    assert client.post(WH_BASE, headers=headers, json=payload).status_code == 201
    payload2 = {"day_of_week": 0, "start_time": "13:00:00", "end_time": "17:00:00"}
    assert client.post(WH_BASE, headers=headers, json=payload2).status_code == 201
    assert mock_schedule.create_working_hour.call_count == 2
    client.close()


# --- Working hours UPDATE / DELETE ---


def test_owner_patch_working_hours() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.update_working_hour.return_value = _working_hour_row(day_of_week=3)
    response = client.patch(
        f"{WH_BASE}/{WH_ID}",
        headers=headers,
        json={"day_of_week": 3},
    )
    assert response.status_code == 200
    mock_schedule.update_working_hour.assert_called_once()
    client.close()


def test_patch_working_hours_move_staff_same_salon() -> None:
    client, mock_schedule, headers = _auth_app(role="admin")
    other_staff = uuid.uuid4()
    mock_schedule.update_working_hour.return_value = _working_hour_row(staff_id=other_staff)
    client.patch(
        f"{WH_BASE}/{WH_ID}",
        headers=headers,
        json={"staff_id": str(other_staff)},
    )
    assert mock_schedule.update_working_hour.call_args.kwargs["salon_id"] == SALON_A
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_patch_working_hours_forbidden(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    assert (
        client.patch(f"{WH_BASE}/{WH_ID}", headers=headers, json={"day_of_week": 1}).status_code
        == 403
    )
    mock_schedule.update_working_hour.assert_not_called()
    client.close()


def test_patch_working_hours_cross_tenant_staff_404() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.update_working_hour.side_effect = ScheduleNotFoundError("staff not found")
    assert (
        client.patch(
            f"{WH_BASE}/{WH_ID}",
            headers=headers,
            json={"staff_id": str(uuid.uuid4())},
        ).status_code
        == 404
    )
    client.close()


def test_delete_working_hours_owner_204() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    response = client.delete(f"{WH_BASE}/{WH_ID}", headers=headers)
    assert response.status_code == 204
    mock_schedule.delete_working_hour.assert_called_once_with(
        salon_id=SALON_A,
        working_hours_id=WH_ID,
    )
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_delete_working_hours_forbidden(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    assert client.delete(f"{WH_BASE}/{WH_ID}", headers=headers).status_code == 403
    mock_schedule.delete_working_hour.assert_not_called()
    client.close()


def test_delete_working_hours_wrong_tenant_404() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.delete_working_hour.side_effect = ScheduleNotFoundError(
        "working hours not found"
    )
    assert client.delete(f"{WH_BASE}/{uuid.uuid4()}", headers=headers).status_code == 404
    client.close()


# --- Blocked periods READ ---


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_blocked_periods_read_roles(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    mock_schedule.list_blocked_periods.return_value = [_blocked_period_row()]
    response = client.get(BP_BASE, headers=headers)
    assert response.status_code == 200
    mock_schedule.list_blocked_periods.assert_called_once()
    client.close()


def test_list_blocked_periods_filters() -> None:
    client, mock_schedule, headers = _auth_app()
    mock_schedule.list_blocked_periods.return_value = []
    response = client.get(
        BP_BASE,
        headers=headers,
        params={
            "staff_id": str(STAFF_ID),
            "starts_from": "2026-01-01T00:00:00+00:00",
            "ends_to": "2026-12-31T23:59:59+00:00",
            "block_type": "holiday",
        },
    )
    assert response.status_code == 200
    kwargs = mock_schedule.list_blocked_periods.call_args.kwargs
    assert kwargs["salon_id"] == SALON_A
    assert kwargs["staff_id"] == STAFF_ID
    assert kwargs["block_type"] == "holiday"
    assert kwargs["starts_from"] is not None
    assert kwargs["ends_to"] is not None
    client.close()


def test_list_blocked_periods_ordering_preserved() -> None:
    client, mock_schedule, headers = _auth_app()
    early = _blocked_period_row(
        id=uuid.uuid4(),
        starts_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    late = _blocked_period_row(
        starts_at=datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc),
    )
    mock_schedule.list_blocked_periods.return_value = [early, late]
    body = client.get(BP_BASE, headers=headers).json()
    assert body[0]["starts_at"] < body[1]["starts_at"]
    client.close()


def test_get_blocked_period_not_found() -> None:
    client, mock_schedule, headers = _auth_app()
    mock_schedule.get_blocked_period.side_effect = ScheduleNotFoundError("blocked period not found")
    assert client.get(f"{BP_BASE}/{BP_ID}", headers=headers).status_code == 404
    client.close()


# --- Blocked periods CREATE ---


def test_create_blocked_period_salon_wide() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.create_blocked_period.return_value = _blocked_period_row()
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "starts_at": "2026-03-01T09:00:00+00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
            "block_type": "holiday",
        },
    )
    assert response.status_code == 201
    call = mock_schedule.create_blocked_period.call_args.kwargs
    assert call["salon_id"] == SALON_A
    assert call["created_by_user_id"] == USER_ID
    client.close()


def test_create_blocked_period_staff_specific() -> None:
    client, mock_schedule, headers = _auth_app(role="admin")
    mock_schedule.create_blocked_period.return_value = _blocked_period_row(staff_id=STAFF_ID)
    client.post(
        BP_BASE,
        headers=headers,
        json={
            "staff_id": str(STAFF_ID),
            "starts_at": "2026-03-01T09:00:00+00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
            "block_type": "time_off",
        },
    )
    assert mock_schedule.create_blocked_period.call_args.kwargs["data"].staff_id == STAFF_ID
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_create_blocked_period_forbidden(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "starts_at": "2026-03-01T09:00:00+00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
        },
    )
    assert response.status_code == 403
    mock_schedule.create_blocked_period.assert_not_called()
    client.close()


def test_create_blocked_period_naive_datetime_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "starts_at": "2026-03-01T09:00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
        },
    )
    assert response.status_code == 422
    client.close()


def test_create_blocked_period_invalid_range_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "starts_at": "2026-03-01T17:00:00+00:00",
            "ends_at": "2026-03-01T09:00:00+00:00",
        },
    )
    assert response.status_code == 422
    client.close()


def test_create_blocked_period_invalid_block_type_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "starts_at": "2026-03-01T09:00:00+00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
            "block_type": "invalid",
        },
    )
    assert response.status_code == 422
    client.close()


def test_create_blocked_period_client_cannot_set_creator_422() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "starts_at": "2026-03-01T09:00:00+00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
            "created_by_user_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422
    mock_schedule.create_blocked_period.assert_not_called()
    client.close()


def test_create_blocked_period_cross_tenant_staff_404() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.create_blocked_period.side_effect = ScheduleNotFoundError("staff not found")
    response = client.post(
        BP_BASE,
        headers=headers,
        json={
            "staff_id": str(uuid.uuid4()),
            "starts_at": "2026-03-01T09:00:00+00:00",
            "ends_at": "2026-03-01T17:00:00+00:00",
        },
    )
    assert response.status_code == 404
    client.close()


# --- Blocked periods UPDATE / DELETE ---


def test_patch_blocked_period_owner() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.update_blocked_period.return_value = _blocked_period_row(reason="Updated")
    response = client.patch(
        f"{BP_BASE}/{BP_ID}",
        headers=headers,
        json={"reason": "Updated"},
    )
    assert response.status_code == 200
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_patch_blocked_period_forbidden(role: str) -> None:
    client, mock_schedule, headers = _auth_app(role=role)
    assert (
        client.patch(f"{BP_BASE}/{BP_ID}", headers=headers, json={"reason": "x"}).status_code
        == 403
    )
    mock_schedule.update_blocked_period.assert_not_called()
    client.close()


def test_patch_blocked_period_cannot_change_creator_422() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    response = client.patch(
        f"{BP_BASE}/{BP_ID}",
        headers=headers,
        json={"created_by_user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    mock_schedule.update_blocked_period.assert_not_called()
    client.close()


def test_delete_blocked_period_admin_204() -> None:
    client, mock_schedule, headers = _auth_app(role="admin")
    response = client.delete(f"{BP_BASE}/{BP_ID}", headers=headers)
    assert response.status_code == 204
    mock_schedule.delete_blocked_period.assert_called_once_with(
        salon_id=SALON_A,
        blocked_period_id=BP_ID,
    )
    client.close()


def test_delete_blocked_period_missing_404() -> None:
    client, mock_schedule, headers = _auth_app(role="owner")
    mock_schedule.delete_blocked_period.side_effect = ScheduleNotFoundError(
        "blocked period not found"
    )
    assert client.delete(f"{BP_BASE}/{uuid.uuid4()}", headers=headers).status_code == 404
    client.close()


# --- ScheduleService unit validation ---


def test_schedule_service_working_hours_validation() -> None:
    svc = ScheduleService(MagicMock())
    with pytest.raises(ScheduleValidationError):
        svc.create_working_hour(
            salon_id=SALON_A,
            data=WorkingHoursCreateData(
                staff_id=None,
                day_of_week=0,
                start_time=time(17, 0),
                end_time=time(9, 0),
            ),
        )


def test_schedule_service_blocked_period_tz_validation() -> None:
    svc = ScheduleService(MagicMock())
    with pytest.raises(ScheduleValidationError):
        svc.create_blocked_period(
            salon_id=SALON_A,
            created_by_user_id=USER_ID,
            data=BlockedPeriodCreateData(
                staff_id=None,
                starts_at=datetime(2026, 1, 1, 10, 0),
                ends_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            ),
        )
