from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_bonus_ledger_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.bonus.errors import (
    BonusLedgerNotFoundError,
    BonusLedgerValidationError,
)
from app.services.bonus.service import BonusLedgerService
from app.services.bonus.types import LedgerTransactionResult

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
CUSTOMER_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
TX_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
NOW = datetime.now(timezone.utc)

LIST_URL = f"/api/v1/salons/{SALON_A}/customers/{CUSTOMER_ID}/bonus-transactions"
ADJ_URL = f"{LIST_URL}/adjustment"


def _ledger_row(**kwargs: object) -> LedgerTransactionResult:
    defaults: dict[str, object] = {
        "transaction_id": TX_ID,
        "salon_id": SALON_A,
        "customer_id": CUSTOMER_ID,
        "booking_id": None,
        "transaction_type": "adjustment",
        "amount_cents": 500,
        "balance_after_cents": 500,
        "description": "Goodwill credit",
        "idempotency_key": None,
        "created_by_user_id": USER_ID,
        "created_at": NOW,
        "idempotent_replay": False,
    }
    defaults.update(kwargs)
    return LedgerTransactionResult(**defaults)


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
    mock_bonus = MagicMock(spec=BonusLedgerService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_bonus_ledger_service] = lambda: mock_bonus
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_bonus, headers


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_bonus_transactions_read_roles(role: str) -> None:
    client, mock_bonus, headers = _auth_app(role=role)
    mock_bonus.list_transactions.return_value = [_ledger_row()]
    try:
        response = client.get(LIST_URL, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == str(TX_ID)
        mock_bonus.list_transactions.assert_called_once_with(
            salon_id=SALON_A,
            customer_id=CUSTOMER_ID,
            limit=50,
            offset=0,
        )
    finally:
        client.close()


def test_list_bonus_transactions_pagination_params() -> None:
    client, mock_bonus, headers = _auth_app()
    mock_bonus.list_transactions.return_value = []
    response = client.get(
        LIST_URL,
        headers=headers,
        params={"limit": 10, "offset": 5},
    )
    assert response.status_code == 200
    mock_bonus.list_transactions.assert_called_once_with(
        salon_id=SALON_A,
        customer_id=CUSTOMER_ID,
        limit=10,
        offset=5,
    )
    client.close()


def test_list_bonus_transactions_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(LIST_URL).status_code == 401


def test_list_customer_not_found_404() -> None:
    client, mock_bonus, headers = _auth_app()
    mock_bonus.list_transactions.side_effect = BonusLedgerNotFoundError(
        "customer not found"
    )
    response = client.get(LIST_URL, headers=headers)
    assert response.status_code == 404
    client.close()


def test_list_cross_tenant_salon_access_denied() -> None:
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
        name="Other",
        slug="other",
        is_active=True,
        timezone="UTC",
        currency_code="KZT",
    )
    mock_auth.get_active_membership.return_value = None
    mock_bonus = MagicMock(spec=BonusLedgerService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_bonus_ledger_service] = lambda: mock_bonus
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/salons/{SALON_B}/customers/{CUSTOMER_ID}/bonus-transactions",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403
    mock_bonus.list_transactions.assert_not_called()


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_adjustment_owner_admin(role: str) -> None:
    client, mock_bonus, headers = _auth_app(role=role)
    mock_bonus.create_adjustment.return_value = _ledger_row(amount_cents=200)
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={"amount_cents": 200, "reason": "Promo credit"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["amount_cents"] == 200
    assert body["created_by_user_id"] == str(USER_ID)
    mock_bonus.create_adjustment.assert_called_once_with(
        salon_id=SALON_A,
        customer_id=CUSTOMER_ID,
        amount_cents=200,
        description="Promo credit",
        created_by_user_id=USER_ID,
    )
    client.close()


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_adjustment_forbidden_for_read_roles(role: str) -> None:
    client, mock_bonus, headers = _auth_app(role=role)
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={"amount_cents": 100, "reason": "Nope"},
    )
    assert response.status_code == 403
    mock_bonus.create_adjustment.assert_not_called()
    client.close()


def test_adjustment_insufficient_balance_422() -> None:
    client, mock_bonus, headers = _auth_app()
    mock_bonus.create_adjustment.side_effect = BonusLedgerValidationError(
        "bonus balance cannot go negative"
    )
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={"amount_cents": -9999, "reason": "Correction"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    client.close()


def test_adjustment_validation_zero_amount() -> None:
    client, mock_bonus, headers = _auth_app()
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={"amount_cents": 0, "reason": "Zero"},
    )
    assert response.status_code == 422
    mock_bonus.create_adjustment.assert_not_called()
    client.close()


def test_adjustment_validation_blank_reason() -> None:
    client, mock_bonus, headers = _auth_app()
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={"amount_cents": 100, "reason": "   "},
    )
    assert response.status_code == 422
    mock_bonus.create_adjustment.assert_not_called()
    client.close()


def test_adjustment_rejects_extra_fields() -> None:
    client, mock_bonus, headers = _auth_app()
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={
            "amount_cents": 100,
            "reason": "OK",
            "salon_id": str(SALON_B),
            "created_by_user_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 422
    mock_bonus.create_adjustment.assert_not_called()
    client.close()


def test_adjustment_customer_not_found_404() -> None:
    client, mock_bonus, headers = _auth_app()
    mock_bonus.create_adjustment.side_effect = BonusLedgerNotFoundError(
        "customer not found"
    )
    response = client.post(
        ADJ_URL,
        headers=headers,
        json={"amount_cents": 50, "reason": "Gift"},
    )
    assert response.status_code == 404
    client.close()
