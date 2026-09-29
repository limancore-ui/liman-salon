from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_customer_service, get_salon_public_service
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.session import engine, get_db
from app.main import create_app
from app.services.customer.service import CustomerService
from app.services.customer.types import PublicCustomerLookupResult
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SLUG_A = "lookup-salon-a"
PHONE = "+77001234567"


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _mock_app() -> tuple[TestClient, MagicMock, MagicMock]:
    app = create_app()
    mock_salon = MagicMock(spec=SalonPublicService)
    mock_customer = MagicMock(spec=CustomerService)
    app.dependency_overrides[get_salon_public_service] = lambda: mock_salon
    app.dependency_overrides[get_customer_service] = lambda: mock_customer
    return TestClient(app), mock_salon, mock_customer


def test_lookup_no_auth_required_response_shape() -> None:
    client, mock_salon, mock_customer = _mock_app()
    mock_salon.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_A,
        slug=SLUG_A,
        name="Salon A",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )
    mock_customer.lookup_public_customer.return_value = PublicCustomerLookupResult(
        found=True,
        full_name="Jane Doe",
    )
    try:
        response = client.get(
            f"/api/v1/public/salons/{SLUG_A}/customer",
            params={"phone": PHONE},
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {"found": True, "full_name": "Jane Doe"}
        assert set(body.keys()) == {"found", "full_name"}
        mock_salon.resolve_public_salon_by_slug.assert_called_once_with(SLUG_A)
        mock_customer.lookup_public_customer.assert_called_once_with(
            salon_id=SALON_A,
            phone=PHONE,
        )
    finally:
        client.close()


def test_lookup_unknown_phone_not_found() -> None:
    client, mock_salon, mock_customer = _mock_app()
    mock_salon.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_A,
        slug=SLUG_A,
        name="Salon A",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )
    mock_customer.lookup_public_customer.return_value = PublicCustomerLookupResult(
        found=False,
        full_name=None,
    )
    response = client.get(
        f"/api/v1/public/salons/{SLUG_A}/customer",
        params={"phone": "+77009999999"},
    )
    assert response.status_code == 200
    assert response.json() == {"found": False, "full_name": None}


def test_lookup_bad_slug_404() -> None:
    client, mock_salon, mock_customer = _mock_app()
    mock_salon.resolve_public_salon_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    response = client.get(
        f"/api/v1/public/salons/unknown-slug/customer",
        params={"phone": PHONE},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    mock_customer.lookup_public_customer.assert_not_called()


def test_lookup_missing_phone_422() -> None:
    client, _mock_salon, mock_customer = _mock_app()
    response = client.get(f"/api/v1/public/salons/{SLUG_A}/customer")
    assert response.status_code == 422
    mock_customer.lookup_public_customer.assert_not_called()


def test_lookup_blank_phone_422() -> None:
    client, _mock_salon, mock_customer = _mock_app()
    response = client.get(
        f"/api/v1/public/salons/{SLUG_A}/customer",
        params={"phone": "   "},
    )
    assert response.status_code == 422
    mock_customer.lookup_public_customer.assert_not_called()


pytestmark_integration = pytest.mark.skipif(
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


def _seed_salon(session: Session, *, salon_id: uuid.UUID, slug: str) -> Salon:
    salon = Salon(
        id=salon_id,
        name=f"Salon {slug}",
        slug=slug,
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()
    return salon


@pytestmark_integration
def test_lookup_same_salon_found_integration(db_session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    slug = f"lookup-int-{suffix}"
    salon = _seed_salon(db_session, salon_id=uuid.uuid4(), slug=slug)
    db_session.add(
        Customer(
            salon_id=salon.id,
            full_name="Returning Guest",
            phone=PHONE,
            email="guest@example.com",
        )
    )
    db_session.flush()

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/public/salons/{slug}/customer",
            params={"phone": PHONE},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["found"] is True
        assert body["full_name"] == "Returning Guest"
        assert "customer_id" not in body
        assert "email" not in body
    finally:
        client.close()
        app.dependency_overrides.clear()


@pytestmark_integration
def test_lookup_other_salon_same_phone_not_found_integration(db_session: Session) -> None:
    suffix = uuid.uuid4().hex[:8]
    slug_a = f"lookup-a-{suffix}"
    slug_b = f"lookup-b-{suffix}"
    salon_a = _seed_salon(db_session, salon_id=uuid.uuid4(), slug=slug_a)
    salon_b = _seed_salon(db_session, salon_id=uuid.uuid4(), slug=slug_b)
    db_session.add(
        Customer(
            salon_id=salon_a.id,
            full_name="Only on A",
            phone=PHONE,
        )
    )
    db_session.flush()

    app = create_app()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    try:
        response = client.get(
            f"/api/v1/public/salons/{slug_b}/customer",
            params={"phone": PHONE},
        )
        assert response.status_code == 200
        assert response.json() == {"found": False, "full_name": None}
    finally:
        client.close()
        app.dependency_overrides.clear()
