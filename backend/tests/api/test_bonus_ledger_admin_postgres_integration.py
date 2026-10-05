"""PostgreSQL integration for bonus ledger admin API (C20.2.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.db.models.bonus_transaction import BonusTransaction
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.user import User
from app.db.session import engine
from app.main import create_app

USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
NOW = datetime.now(timezone.utc)


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL test database not reachable",
)


@pytest.fixture
def db_session() -> Session:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _authed_client(
    db_session: Session,
    *,
    salon: Salon,
    role: str = "owner",
) -> tuple[TestClient, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon.id,
        name=salon.name,
        slug=salon.slug,
        is_active=True,
        timezone=salon.timezone,
        currency_code=salon.currency_code,
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon.id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def _ensure_audit_user(session: Session) -> None:
    existing = session.get(User, USER_ID)
    if existing is not None:
        return
    session.add(
        User(
            id=USER_ID,
            email="bonus-audit@example.com",
            full_name="Bonus Audit User",
            is_active=True,
        )
    )
    session.flush()


def _seed_salon_with_customer(session: Session) -> tuple[Salon, Customer]:
    _ensure_audit_user(session)
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Bonus API {suffix}",
        slug=f"bonus-api-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()
    customer = Customer(
        salon_id=salon.id,
        full_name="Ledger Guest",
        phone=f"+7701{suffix}",
        bonus_balance_cents=1_000,
    )
    session.add(customer)
    session.flush()
    return salon, customer


def _list_url(salon_id: uuid.UUID, customer_id: uuid.UUID) -> str:
    return (
        f"/api/v1/salons/{salon_id}/customers/{customer_id}/bonus-transactions"
    )


def _adj_url(salon_id: uuid.UUID, customer_id: uuid.UUID) -> str:
    return f"{_list_url(salon_id, customer_id)}/adjustment"


def test_postgres_adjustment_success_and_ledger_read(
    db_session: Session,
) -> None:
    salon, customer = _seed_salon_with_customer(db_session)
    client, headers = _authed_client(db_session, salon=salon)
    try:
        response = client.post(
            _adj_url(salon.id, customer.id),
            headers=headers,
            json={"amount_cents": 250, "reason": "Manual top-up"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["transaction_type"] == "adjustment"
        assert body["amount_cents"] == 250
        assert body["balance_after_cents"] == 1_250
        assert body["created_by_user_id"] == str(USER_ID)
        assert body["description"] == "Manual top-up"

        listed = client.get(_list_url(salon.id, customer.id), headers=headers)
        assert listed.status_code == 200
        rows = listed.json()
        assert len(rows) == 1
        assert rows[0]["id"] == body["id"]

        db_session.refresh(customer)
        assert customer.bonus_balance_cents == 1_250
    finally:
        client.close()


def test_postgres_insufficient_balance_rejected(db_session: Session) -> None:
    salon, customer = _seed_salon_with_customer(db_session)
    client, headers = _authed_client(db_session, salon=salon)
    try:
        response = client.post(
            _adj_url(salon.id, customer.id),
            headers=headers,
            json={"amount_cents": -5_000, "reason": "Over debit"},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        db_session.refresh(customer)
        assert customer.bonus_balance_cents == 1_000
        assert db_session.scalars(select(BonusTransaction)).all() == []
    finally:
        client.close()


def test_postgres_list_pagination_and_order(db_session: Session) -> None:
    salon, customer = _seed_salon_with_customer(db_session)
    client, headers = _authed_client(db_session, salon=salon)
    try:
        tx_ids: list[uuid.UUID] = []
        for amount, reason in (
            (100, "First"),
            (200, "Second"),
            (300, "Third"),
        ):
            resp = client.post(
                _adj_url(salon.id, customer.id),
                headers=headers,
                json={"amount_cents": amount, "reason": reason},
            )
            assert resp.status_code == 201
            tx_ids.append(uuid.UUID(resp.json()["id"]))

        base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        for index, tx_id in enumerate(tx_ids):
            tx = db_session.get(BonusTransaction, tx_id)
            assert tx is not None
            tx.created_at = base + timedelta(seconds=index)
        db_session.flush()

        page = client.get(
            _list_url(salon.id, customer.id),
            headers=headers,
            params={"limit": 2, "offset": 0},
        )
        assert page.status_code == 200
        rows = page.json()
        assert len(rows) == 2
        assert rows[0]["description"] == "Third"
        assert rows[1]["description"] == "Second"

        page2 = client.get(
            _list_url(salon.id, customer.id),
            headers=headers,
            params={"limit": 2, "offset": 2},
        )
        assert page2.status_code == 200
        assert len(page2.json()) == 1
        assert page2.json()[0]["description"] == "First"
    finally:
        client.close()


def test_postgres_tenant_isolation_customer_not_in_other_salon(
    db_session: Session,
) -> None:
    salon_a, customer_a = _seed_salon_with_customer(db_session)
    salon_b, _customer_b = _seed_salon_with_customer(db_session)
    client, headers = _authed_client(db_session, salon=salon_b)
    try:
        response = client.get(
            _list_url(salon_b.id, customer_a.id),
            headers=headers,
        )
        assert response.status_code == 404
        assert salon_a.id != salon_b.id
    finally:
        client.close()
