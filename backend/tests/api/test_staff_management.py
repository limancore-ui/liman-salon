from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_staff_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.staff.errors import StaffNotFoundError, StaffValidationError
from app.services.staff.service import StaffService

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
STAFF_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime.now(timezone.utc)


def _staff_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": STAFF_ID,
        "salon_id": SALON_A,
        "display_name": "Alex",
        "title": "Stylist",
        "bio": None,
        "color_hex": "#AABBCC",
        "is_bookable": True,
        "is_active": True,
        "sort_order": 0,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _auth_app(*, role: str = "owner", salon_id: uuid.UUID = SALON_A) -> tuple[TestClient, MagicMock]:
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
    mock_staff = MagicMock(spec=StaffService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_staff_service] = lambda: mock_staff
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_staff, headers


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_staff_read_roles(role: str) -> None:
    client, mock_staff, headers = _auth_app(role=role)
    mock_staff.list_staff.return_value = [_staff_row()]
    try:
        response = client.get(f"/api/v1/salons/{SALON_A}/staff", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_staff.list_staff.assert_called_once_with(
            salon_id=SALON_A,
            active_only=True,
            bookable_only=False,
        )
    finally:
        client.close()


def test_list_staff_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/staff").status_code == 401


def test_list_staff_no_membership_403() -> None:
    client, _, headers = _auth_app(role="owner")
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
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as c:
        r = c.get(
            f"/api/v1/salons/{SALON_A}/staff",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
        assert r.json()["code"] == "salon_access_denied"


def test_get_staff_detail_tenant_scoped() -> None:
    client, mock_staff, headers = _auth_app()
    mock_staff.get_staff.return_value = _staff_row()
    response = client.get(
        f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 200
    mock_staff.get_staff.assert_called_once_with(salon_id=SALON_A, staff_id=STAFF_ID)


def test_get_staff_not_found_404() -> None:
    client, mock_staff, headers = _auth_app()
    mock_staff.get_staff.side_effect = StaffNotFoundError("staff not found")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 404


def test_wrong_tenant_staff_404() -> None:
    client, mock_staff, headers = _auth_app(salon_id=SALON_A)
    mock_staff.get_staff.side_effect = StaffNotFoundError("staff not found")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/staff/{uuid.uuid4()}",
        headers=headers,
    )
    assert response.status_code == 404
    assert mock_staff.get_staff.call_args.kwargs["salon_id"] == SALON_A


def test_owner_can_create() -> None:
    client, mock_staff, headers = _auth_app(role="owner")
    mock_staff.create_staff.return_value = _staff_row(display_name="New")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/staff",
        headers=headers,
        json={"display_name": "New"},
    )
    assert response.status_code == 201
    assert mock_staff.create_staff.call_args.kwargs["salon_id"] == SALON_A


def test_admin_can_create() -> None:
    client, mock_staff, headers = _auth_app(role="admin")
    mock_staff.create_staff.return_value = _staff_row()
    assert (
        client.post(
            f"/api/v1/salons/{SALON_A}/staff",
            headers=headers,
            json={"display_name": "X"},
        ).status_code
        == 201
    )


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_create_forbidden_for_non_admin(role: str) -> None:
    client, mock_staff, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/staff",
        headers=headers,
        json={"display_name": "X"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    mock_staff.create_staff.assert_not_called()


def test_create_validation_blank_name_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/staff",
        headers=headers,
        json={"display_name": "   "},
    )
    assert response.status_code == 422


def test_create_invalid_color_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/staff",
        headers=headers,
        json={"display_name": "A", "color_hex": "red"},
    )
    assert response.status_code == 422


def test_create_negative_sort_order_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/staff",
        headers=headers,
        json={"display_name": "A", "sort_order": -1},
    )
    assert response.status_code == 422


def test_body_cannot_override_salon_id() -> None:
    client, mock_staff, headers = _auth_app(role="owner", salon_id=SALON_A)
    mock_staff.create_staff.return_value = _staff_row()
    client.post(
        f"/api/v1/salons/{SALON_A}/staff",
        headers=headers,
        json={"display_name": "A", "salon_id": str(SALON_B)},
    )
    assert mock_staff.create_staff.call_args.kwargs["salon_id"] == SALON_A


def test_owner_can_update() -> None:
    client, mock_staff, headers = _auth_app(role="owner")
    mock_staff.update_staff.return_value = _staff_row(display_name="Updated")
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
        headers=headers,
        json={"display_name": "Updated"},
    )
    assert response.status_code == 200


def test_staff_cannot_update_403() -> None:
    client, mock_staff, headers = _auth_app(role="staff")
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
        headers=headers,
        json={"display_name": "Updated"},
    )
    assert response.status_code == 403
    mock_staff.update_staff.assert_not_called()


def test_soft_deactivate_via_patch() -> None:
    client, mock_staff, headers = _auth_app(role="admin")
    mock_staff.update_staff.return_value = _staff_row(is_active=False)
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert mock_staff.update_staff.call_args.kwargs["data"].is_active is False


def test_no_delete_endpoint() -> None:
    client, _, headers = _auth_app()
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 405


def test_service_create_defaults_and_validation() -> None:
    from app.services.staff.service import StaffCreateData

    svc = StaffService(MagicMock())
    with pytest.raises(StaffValidationError):
        svc.create_staff(
            salon_id=SALON_A,
            data=StaffCreateData(display_name="A", color_hex="#GGGGGG"),
        )
    with pytest.raises(StaffValidationError):
        svc.create_staff(
            salon_id=SALON_A,
            data=StaffCreateData(display_name="A", sort_order=-1),
        )


def test_admin_can_update() -> None:
    client, mock_staff, headers = _auth_app(role="admin")
    mock_staff.update_staff.return_value = _staff_row()
    assert (
        client.patch(
            f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
            headers=headers,
            json={"title": "Lead"},
        ).status_code
        == 200
    )


def test_receptionist_cannot_update_403() -> None:
    client, mock_staff, headers = _auth_app(role="receptionist")
    assert (
        client.patch(
            f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
            headers=headers,
            json={"title": "Lead"},
        ).status_code
        == 403
    )
    mock_staff.update_staff.assert_not_called()


def test_update_wrong_tenant_404() -> None:
    client, mock_staff, headers = _auth_app(role="owner", salon_id=SALON_A)
    mock_staff.update_staff.side_effect = StaffNotFoundError("staff not found")
    assert (
        client.patch(
            f"/api/v1/salons/{SALON_A}/staff/{STAFF_ID}",
            headers=headers,
            json={"is_active": False},
        ).status_code
        == 404
    )
    assert mock_staff.update_staff.call_args.kwargs["salon_id"] == SALON_A


def test_cannot_create_in_salon_b_without_membership() -> None:
    client, mock_staff, headers = _auth_app(role="owner", salon_id=SALON_A)
    app = client.app
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="o@e.com",
        full_name="O",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B,
        name="B",
        slug="b",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    r = client.post(
        f"/api/v1/salons/{SALON_B}/staff",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Intruder"},
    )
    assert r.status_code == 403
    mock_staff.create_staff.assert_not_called()
