from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_service_catalog_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.service_catalog.errors import (
    ServiceCatalogNotFoundError,
    ServiceCatalogValidationError,
)
from app.services.service_catalog.service import ServiceCatalogService, ServiceCreateData

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SERVICE_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
STAFF_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime.now(timezone.utc)


def _service_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": SERVICE_ID,
        "salon_id": SALON_A,
        "name": "Cut",
        "description": None,
        "duration_minutes": 30,
        "buffer_before_minutes": 0,
        "buffer_after_minutes": 0,
        "price_cents": 2500,
        "is_active": True,
        "sort_order": 0,
        "created_at": NOW,
        "updated_at": NOW,
        "salon": SimpleNamespace(currency_code="USD"),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


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
    mock_catalog = MagicMock(spec=ServiceCatalogService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_service_catalog_service] = lambda: mock_catalog
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_catalog, headers


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_services_read_roles(role: str) -> None:
    client, mock_catalog, headers = _auth_app(role=role)
    mock_catalog.list_services.return_value = [_service_row()]
    try:
        response = client.get(f"/api/v1/salons/{SALON_A}/services", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["currency_code"] == "USD"
        mock_catalog.list_services.assert_called_once_with(
            salon_id=SALON_A,
            active_only=True,
        )
    finally:
        client.close()


def test_list_services_active_only_query() -> None:
    client, mock_catalog, headers = _auth_app()
    mock_catalog.list_services.return_value = []
    response = client.get(
        f"/api/v1/salons/{SALON_A}/services?active_only=false",
        headers=headers,
    )
    assert response.status_code == 200
    mock_catalog.list_services.assert_called_once_with(
        salon_id=SALON_A,
        active_only=False,
    )
    client.close()


def test_list_services_sort_order_preserved() -> None:
    client, mock_catalog, headers = _auth_app()
    mock_catalog.list_services.return_value = [
        _service_row(name="A", sort_order=0),
        _service_row(id=uuid.uuid4(), name="B", sort_order=1),
    ]
    response = client.get(f"/api/v1/salons/{SALON_A}/services", headers=headers)
    names = [item["name"] for item in response.json()]
    assert names == ["A", "B"]
    client.close()


def test_list_services_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/services").status_code == 401


def test_get_service_detail_tenant_scoped() -> None:
    client, mock_catalog, headers = _auth_app()
    mock_catalog.get_service.return_value = _service_row()
    response = client.get(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}",
        headers=headers,
    )
    assert response.status_code == 200
    mock_catalog.get_service.assert_called_once_with(
        salon_id=SALON_A,
        service_id=SERVICE_ID,
    )
    client.close()


def test_get_service_not_found_404() -> None:
    client, mock_catalog, headers = _auth_app()
    mock_catalog.get_service.side_effect = ServiceCatalogNotFoundError("service not found")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}",
        headers=headers,
    )
    assert response.status_code == 404
    client.close()


def test_wrong_tenant_service_404() -> None:
    client, mock_catalog, headers = _auth_app(salon_id=SALON_A)
    mock_catalog.get_service.side_effect = ServiceCatalogNotFoundError("service not found")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/services/{uuid.uuid4()}",
        headers=headers,
    )
    assert response.status_code == 404
    assert mock_catalog.get_service.call_args.kwargs["salon_id"] == SALON_A
    client.close()


def test_owner_can_create_service() -> None:
    client, mock_catalog, headers = _auth_app(role="owner")
    mock_catalog.create_service.return_value = _service_row(name="New")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/services",
        headers=headers,
        json={"name": "New", "duration_minutes": 45, "price_cents": 1000},
    )
    assert response.status_code == 201
    assert mock_catalog.create_service.call_args.kwargs["salon_id"] == SALON_A
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_create_service_forbidden_for_non_admin(role: str) -> None:
    client, mock_catalog, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/services",
        headers=headers,
        json={"name": "X", "duration_minutes": 30},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    mock_catalog.create_service.assert_not_called()
    client.close()


def test_create_validation_blank_name_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/services",
        headers=headers,
        json={"name": "   ", "duration_minutes": 30},
    )
    assert response.status_code == 422
    client.close()


def test_create_invalid_duration_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/services",
        headers=headers,
        json={"name": "Cut", "duration_minutes": 0},
    )
    assert response.status_code == 422
    client.close()


def test_create_negative_sort_order_422() -> None:
    client, _, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/services",
        headers=headers,
        json={"name": "Cut", "duration_minutes": 30, "sort_order": -1},
    )
    assert response.status_code == 422
    client.close()


def test_body_cannot_override_salon_id_on_create() -> None:
    client, mock_catalog, headers = _auth_app(role="owner", salon_id=SALON_A)
    mock_catalog.create_service.return_value = _service_row()
    client.post(
        f"/api/v1/salons/{SALON_A}/services",
        headers=headers,
        json={"name": "Cut", "duration_minutes": 30, "salon_id": str(SALON_B)},
    )
    assert mock_catalog.create_service.call_args.kwargs["salon_id"] == SALON_A
    client.close()


def test_soft_deactivate_via_patch() -> None:
    client, mock_catalog, headers = _auth_app(role="admin")
    mock_catalog.update_service.return_value = _service_row(is_active=False)
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert mock_catalog.update_service.call_args.kwargs["data"].is_active is False
    client.close()


def test_staff_cannot_update_service_403() -> None:
    client, mock_catalog, headers = _auth_app(role="staff")
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}",
        headers=headers,
        json={"name": "Updated"},
    )
    assert response.status_code == 403
    mock_catalog.update_service.assert_not_called()
    client.close()


def test_delete_service_endpoint_405() -> None:
    client, _, headers = _auth_app()
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}",
        headers=headers,
    )
    assert response.status_code == 405
    client.close()


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_service_staff_read_roles(role: str) -> None:
    client, mock_catalog, headers = _auth_app(role=role)
    mock_catalog.list_service_staff.return_value = [_staff_row()]
    response = client.get(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff",
        headers=headers,
    )
    assert response.status_code == 200
    mock_catalog.list_service_staff.assert_called_once_with(
        salon_id=SALON_A,
        service_id=SERVICE_ID,
    )
    client.close()


def test_owner_can_attach_staff() -> None:
    client, mock_catalog, headers = _auth_app(role="owner")
    mock_catalog.attach_staff_to_service.return_value = _staff_row()
    response = client.put(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 200
    assert mock_catalog.attach_staff_to_service.call_args.kwargs["salon_id"] == SALON_A
    client.close()


def test_attach_staff_idempotent_put() -> None:
    client, mock_catalog, headers = _auth_app(role="admin")
    mock_catalog.attach_staff_to_service.return_value = _staff_row()
    path = f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff/{STAFF_ID}"
    assert client.put(path, headers=headers).status_code == 200
    assert client.put(path, headers=headers).status_code == 200
    assert mock_catalog.attach_staff_to_service.call_count == 2
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_attach_staff_forbidden_for_non_admin(role: str) -> None:
    client, mock_catalog, headers = _auth_app(role=role)
    response = client.put(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 403
    mock_catalog.attach_staff_to_service.assert_not_called()
    client.close()


def test_attach_staff_not_found_404() -> None:
    client, mock_catalog, headers = _auth_app(role="owner")
    mock_catalog.attach_staff_to_service.side_effect = ServiceCatalogNotFoundError(
        "staff not found"
    )
    response = client.put(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 404
    client.close()


def test_admin_can_detach_staff_204() -> None:
    client, mock_catalog, headers = _auth_app(role="admin")
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 204
    mock_catalog.detach_staff_from_service.assert_called_once_with(
        salon_id=SALON_A,
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
    )
    client.close()


def test_detach_missing_relationship_404() -> None:
    client, mock_catalog, headers = _auth_app(role="owner")
    mock_catalog.detach_staff_from_service.side_effect = ServiceCatalogNotFoundError(
        "staff-service relationship not found"
    )
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/services/{SERVICE_ID}/staff/{STAFF_ID}",
        headers=headers,
    )
    assert response.status_code == 404
    client.close()


def test_service_catalog_service_validation() -> None:
    svc = ServiceCatalogService(MagicMock())
    with pytest.raises(ServiceCatalogValidationError):
        svc.create_service(
            salon_id=SALON_A,
            data=ServiceCreateData(name="Cut", duration_minutes=0),
        )
    with pytest.raises(ServiceCatalogValidationError):
        svc.create_service(
            salon_id=SALON_A,
            data=ServiceCreateData(name="Cut", sort_order=-1),
        )
