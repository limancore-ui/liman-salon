from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_customer_service
from app.main import create_app
from app.services.customer.errors import CustomerConflictError, CustomerValidationError
from app.services.customer.service import CustomerService
from app.services.customer.types import CustomerResolveResult

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CUSTOMER_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")


def _public_app() -> tuple[TestClient, MagicMock]:
    app = create_app()
    mock_customer = MagicMock(spec=CustomerService)
    app.dependency_overrides[get_customer_service] = lambda: mock_customer
    return TestClient(app), mock_customer


def test_resolve_no_auth_required() -> None:
    client, mock_customer = _public_app()
    mock_customer.resolve_public_customer.return_value = CustomerResolveResult(
        customer_id=CUSTOMER_ID,
        created=True,
    )
    try:
        response = client.post(
            f"/api/v1/salons/{SALON_A}/public/customers/resolve",
            json={"full_name": "Jane", "phone": "+77001234567"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {"customer_id": str(CUSTOMER_ID), "created": True}
        assert set(body.keys()) == {"customer_id", "created"}
        mock_customer.resolve_public_customer.assert_called_once()
        assert mock_customer.resolve_public_customer.call_args.kwargs["salon_id"] == SALON_A
    finally:
        client.close()


def test_resolve_existing_created_false() -> None:
    client, mock_customer = _public_app()
    mock_customer.resolve_public_customer.return_value = CustomerResolveResult(
        customer_id=CUSTOMER_ID,
        created=False,
    )
    response = client.post(
        f"/api/v1/salons/{SALON_A}/public/customers/resolve",
        json={"full_name": "Other Name", "phone": "+77001234567"},
    )
    assert response.status_code == 200
    assert response.json()["created"] is False


def test_resolve_extra_fields_forbidden() -> None:
    client, mock_customer = _public_app()
    response = client.post(
        f"/api/v1/salons/{SALON_A}/public/customers/resolve",
        json={
            "full_name": "Jane",
            "phone": "+77001234567",
            "notes": "secret",
        },
    )
    assert response.status_code == 422
    mock_customer.resolve_public_customer.assert_not_called()


def test_resolve_missing_phone_422() -> None:
    client, mock_customer = _public_app()
    response = client.post(
        f"/api/v1/salons/{SALON_A}/public/customers/resolve",
        json={"full_name": "Jane"},
    )
    assert response.status_code == 422
    mock_customer.resolve_public_customer.assert_not_called()


def test_resolve_conflict_409() -> None:
    client, mock_customer = _public_app()
    mock_customer.resolve_public_customer.side_effect = CustomerConflictError("conflict")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/public/customers/resolve",
        json={
            "full_name": "Jane",
            "phone": "+77001234567",
            "email": "taken@example.com",
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_resolve_validation_422() -> None:
    client, mock_customer = _public_app()
    mock_customer.resolve_public_customer.side_effect = CustomerValidationError("bad phone")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/public/customers/resolve",
        json={"full_name": "Jane", "phone": "+77001234567"},
    )
    assert response.status_code == 422
