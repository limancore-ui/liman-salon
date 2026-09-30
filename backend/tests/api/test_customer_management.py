from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_customer_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.customer.errors import (
    CustomerConflictError,
    CustomerNotFoundError,
    CustomerValidationError,
)
from app.services.customer.service import CustomerCreateData, CustomerService

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CUSTOMER_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime.now(timezone.utc)


def _customer_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": CUSTOMER_ID,
        "salon_id": SALON_A,
        "user_id": None,
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+77001234567",
        "notes": None,
        "bonus_balance_cents": 0,
        "marketing_opt_in": False,
        "whatsapp_opt_in": False,
        "whatsapp_opt_in_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _auth_app(*, role: str = "owner", salon_id: uuid.UUID = SALON_A) -> tuple[TestClient, MagicMock, dict[str, str]]:
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
    mock_customer = MagicMock(spec=CustomerService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_customer_service] = lambda: mock_customer
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_customer, headers


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_customers_read_roles(role: str) -> None:
    client, mock_customer, headers = _auth_app(role=role)
    mock_customer.list_customers.return_value = [_customer_row()]
    try:
        response = client.get(f"/api/v1/salons/{SALON_A}/customers", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_customer.list_customers.assert_called_once()
        assert mock_customer.list_customers.call_args.kwargs["salon_id"] == SALON_A
    finally:
        client.close()


def test_list_customers_query_params() -> None:
    client, mock_customer, headers = _auth_app()
    mock_customer.list_customers.return_value = []
    response = client.get(
        f"/api/v1/salons/{SALON_A}/customers",
        headers=headers,
        params={"q": "jane", "limit": 10, "offset": 5, "sort": "-id"},
    )
    assert response.status_code == 200
    mock_customer.list_customers.assert_called_once_with(
        salon_id=SALON_A,
        q="jane",
        limit=10,
        offset=5,
        sort="-id",
    )


def test_list_customers_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/customers").status_code == 401


def test_get_customer_detail() -> None:
    client, mock_customer, headers = _auth_app()
    mock_customer.get_customer.return_value = _customer_row()
    response = client.get(
        f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}",
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(CUSTOMER_ID)
    assert body["bonus_balance_cents"] == 0
    mock_customer.get_customer.assert_called_once_with(
        salon_id=SALON_A,
        customer_id=CUSTOMER_ID,
    )


def test_get_customer_not_found_404() -> None:
    client, mock_customer, headers = _auth_app()
    mock_customer.get_customer.side_effect = CustomerNotFoundError("customer not found")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}",
        headers=headers,
    )
    assert response.status_code == 404


def test_owner_can_create() -> None:
    client, mock_customer, headers = _auth_app(role="owner")
    mock_customer.create_customer.return_value = _customer_row(full_name="New")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/customers",
        headers=headers,
        json={"full_name": "New", "phone": "+77009998877"},
    )
    assert response.status_code == 201
    assert mock_customer.create_customer.call_args.kwargs["salon_id"] == SALON_A


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_create_forbidden_for_non_admin(role: str) -> None:
    client, mock_customer, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/customers",
        headers=headers,
        json={"full_name": "X"},
    )
    assert response.status_code == 403
    mock_customer.create_customer.assert_not_called()


def test_create_rejects_extra_fields() -> None:
    client, mock_customer, headers = _auth_app(role="owner")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/customers",
        headers=headers,
        json={"full_name": "A", "user_id": str(USER_ID), "bonus_balance_cents": 100},
    )
    assert response.status_code == 422
    mock_customer.create_customer.assert_not_called()


def test_create_conflict_409() -> None:
    client, mock_customer, headers = _auth_app(role="owner")
    mock_customer.create_customer.side_effect = CustomerConflictError("conflict")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/customers",
        headers=headers,
        json={"full_name": "A", "email": "dup@example.com"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_owner_can_update() -> None:
    client, mock_customer, headers = _auth_app(role="owner")
    mock_customer.update_customer.return_value = _customer_row(full_name="Updated")
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}",
        headers=headers,
        json={"full_name": "Updated"},
    )
    assert response.status_code == 200


def test_staff_cannot_update_403() -> None:
    client, mock_customer, headers = _auth_app(role="staff")
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}",
        headers=headers,
        json={"full_name": "Updated"},
    )
    assert response.status_code == 403
    mock_customer.update_customer.assert_not_called()


def test_update_rejects_bonus_and_user_id() -> None:
    client, mock_customer, headers = _auth_app(role="owner")
    response = client.patch(
        f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}",
        headers=headers,
        json={"bonus_balance_cents": 50, "user_id": str(USER_ID)},
    )
    assert response.status_code == 422
    mock_customer.update_customer.assert_not_called()


def test_no_delete_endpoint() -> None:
    client, _, headers = _auth_app()
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}",
        headers=headers,
    )
    assert response.status_code == 405


def test_body_cannot_override_salon_id() -> None:
    client, mock_customer, headers = _auth_app(role="owner", salon_id=SALON_A)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/customers",
        headers=headers,
        json={"full_name": "A", "salon_id": str(SALON_B)},
    )
    assert response.status_code == 422
    mock_customer.create_customer.assert_not_called()


def test_service_create_validation() -> None:
    svc = CustomerService(MagicMock())
    with pytest.raises(CustomerValidationError):
        svc.create_customer(
            salon_id=SALON_A,
            data=CustomerCreateData(full_name="   "),
            clock=lambda: NOW,
        )
