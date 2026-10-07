"""HTTP-level checks that Kyrgyz phone canonicalization is enforced end to end.

Real ``CustomerService`` / ``PublicBookingOrchestrator`` are used; repositories and
neighbouring services are mocked, so no database is required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_as_of,
    get_customer_service,
    get_public_booking_orchestrator,
    get_salon_public_service,
)
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.customer.service import CustomerService
from app.services.public_booking.orchestrator import PublicBookingOrchestrator
from app.services.public_booking.types import PublicBookingResult
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

from tests.api.conftest import FIXED_AS_OF

SALON_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
CUSTOMER_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
STAFF_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SERVICE_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
BOOKING_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
SLUG = "liman-demo"
NOW = datetime.now(timezone.utc)
SERVICE_START = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
CANONICAL = "+996555123456"
BAD_PHONES = ["+77001234567", "+998901234567", "55512345", "55512345a", "5551234567"]


def _real_customer_service() -> CustomerService:
    svc = CustomerService(MagicMock())
    svc._repo.get_customer_by_phone = MagicMock(return_value=None)

    def _add(customer: object) -> object:
        customer.id = CUSTOMER_ID  # type: ignore[attr-defined]
        return customer

    svc._repo.add_customer = MagicMock(side_effect=_add)
    return svc


def _salon_public() -> MagicMock:
    mock = MagicMock(spec=SalonPublicService)
    mock.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug=SLUG,
        name="Demo",
        currency_code="KGS",
        timezone="Asia/Bishkek",
    )
    return mock


# --- public resolve ---------------------------------------------------------


def test_public_resolve_accepts_local_digits_and_stores_canonical() -> None:
    app = create_app()
    svc = _real_customer_service()
    app.dependency_overrides[get_customer_service] = lambda: svc
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/public/customers/resolve",
            json={"full_name": "Jane", "phone": "555123456"},
        )
    assert response.status_code == 200
    assert svc._repo.add_customer.call_args[0][0].phone == CANONICAL
    svc._repo.get_customer_by_phone.assert_called_once_with(
        salon_id=SALON_ID, phone=CANONICAL
    )


@pytest.mark.parametrize("phone", BAD_PHONES)
def test_public_resolve_rejects_invalid_phone(phone: str) -> None:
    app = create_app()
    svc = _real_customer_service()
    app.dependency_overrides[get_customer_service] = lambda: svc
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/public/customers/resolve",
            json={"full_name": "Jane", "phone": phone},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    svc._repo.add_customer.assert_not_called()


# --- public lookup ----------------------------------------------------------


def test_public_lookup_canonicalizes_before_query() -> None:
    app = create_app()
    svc = _real_customer_service()
    app.dependency_overrides[get_customer_service] = lambda: svc
    app.dependency_overrides[get_salon_public_service] = _salon_public
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/customer",
            params={"phone": "555123456"},
        )
    assert response.status_code == 200
    assert response.json() == {"found": False, "full_name": None}
    svc._repo.get_customer_by_phone.assert_called_once_with(
        salon_id=SALON_ID, phone=CANONICAL
    )


def test_public_lookup_accepts_canonical_value() -> None:
    app = create_app()
    svc = _real_customer_service()
    app.dependency_overrides[get_customer_service] = lambda: svc
    app.dependency_overrides[get_salon_public_service] = _salon_public
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/customer",
            params={"phone": CANONICAL},
        )
    assert response.status_code == 200
    svc._repo.get_customer_by_phone.assert_called_once_with(
        salon_id=SALON_ID, phone=CANONICAL
    )


@pytest.mark.parametrize("phone", BAD_PHONES)
def test_public_lookup_rejects_invalid_phone(phone: str) -> None:
    app = create_app()
    svc = _real_customer_service()
    app.dependency_overrides[get_customer_service] = lambda: svc
    app.dependency_overrides[get_salon_public_service] = _salon_public
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/public/salons/{SLUG}/customer",
            params={"phone": phone},
        )
    assert response.status_code == 422
    svc._repo.get_customer_by_phone.assert_not_called()


# --- public booking orchestrator -------------------------------------------


def _booking_client() -> tuple[TestClient, CustomerService, MagicMock]:
    app = create_app()
    svc = _real_customer_service()
    public_booking = MagicMock()
    public_booking.create_public_booking.return_value = PublicBookingResult(
        booking_id=BOOKING_ID,
        status="pending",
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_START + timedelta(hours=1),
        hold_expires_at=FIXED_AS_OF + timedelta(seconds=900),
        manage_token="token",
    )
    orch = PublicBookingOrchestrator(_salon_public(), svc, public_booking)
    app.dependency_overrides[get_public_booking_orchestrator] = lambda: orch
    app.dependency_overrides[get_as_of] = lambda: FIXED_AS_OF
    return TestClient(app), svc, public_booking


def _booking_payload(phone: str) -> dict:
    return {
        "full_name": "Jane",
        "phone": phone,
        "service_id": str(SERVICE_ID),
        "staff_id": str(STAFF_ID),
        "service_start": SERVICE_START.isoformat(),
    }


@pytest.mark.parametrize("phone", ["555123456", CANONICAL])
def test_public_booking_stores_canonical_phone(phone: str) -> None:
    client, svc, public_booking = _booking_client()
    with client:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings",
            json=_booking_payload(phone),
        )
    assert response.status_code == 201
    assert svc._repo.add_customer.call_args[0][0].phone == CANONICAL
    public_booking.create_public_booking.assert_called_once()


@pytest.mark.parametrize("phone", BAD_PHONES)
def test_public_booking_rejects_invalid_phone_before_booking(phone: str) -> None:
    client, svc, public_booking = _booking_client()
    with client:
        response = client.post(
            f"/api/v1/public/salons/{SLUG}/bookings",
            json=_booking_payload(phone),
        )
    assert response.status_code == 422
    svc._repo.add_customer.assert_not_called()
    public_booking.create_public_booking.assert_not_called()


# --- admin POST / PATCH -----------------------------------------------------


def _admin_client() -> tuple[TestClient, CustomerService, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID, email="o@example.com", full_name="Owner", is_active=True
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_ID,
        name="Salon",
        slug="salon",
        is_active=True,
        timezone="UTC",
        currency_code="KGS",
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=SALON_ID, user_id=USER_ID, role="owner", is_active=True
    )
    svc = CustomerService(MagicMock())

    def _add(customer: object) -> SimpleNamespace:
        return _row(
            full_name=customer.full_name,  # type: ignore[attr-defined]
            phone=customer.phone,  # type: ignore[attr-defined]
        )

    svc._repo.add_customer = MagicMock(side_effect=_add)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_customer_service] = lambda: svc
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    return TestClient(app), svc, {"Authorization": f"Bearer {token}"}


def _row(**kwargs: object) -> SimpleNamespace:
    base = {
        "id": CUSTOMER_ID,
        "salon_id": SALON_ID,
        "user_id": None,
        "full_name": "Jane",
        "email": None,
        "phone": "+996700000000",
        "notes": None,
        "bonus_balance_cents": 0,
        "marketing_opt_in": False,
        "whatsapp_opt_in": False,
        "whatsapp_opt_in_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_admin_post_canonicalizes_phone() -> None:
    client, _svc, headers = _admin_client()
    with client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/customers",
            headers=headers,
            json={"full_name": "Jane", "phone": "555123456"},
        )
    assert response.status_code == 201
    assert response.json()["phone"] == CANONICAL


@pytest.mark.parametrize("phone", BAD_PHONES)
def test_admin_post_rejects_invalid_phone(phone: str) -> None:
    client, svc, headers = _admin_client()
    with client:
        response = client.post(
            f"/api/v1/salons/{SALON_ID}/customers",
            headers=headers,
            json={"full_name": "Jane", "phone": phone},
        )
    assert response.status_code == 422
    svc._repo.add_customer.assert_not_called()


def test_admin_patch_canonicalizes_phone() -> None:
    client, svc, headers = _admin_client()
    svc._repo.get_customer_by_id = MagicMock(return_value=_row())
    svc._repo.flush = MagicMock()
    with client:
        response = client.patch(
            f"/api/v1/salons/{SALON_ID}/customers/{CUSTOMER_ID}",
            headers=headers,
            json={"phone": "555123456"},
        )
    assert response.status_code == 200
    assert response.json()["phone"] == CANONICAL


@pytest.mark.parametrize("phone", BAD_PHONES)
def test_admin_patch_rejects_invalid_phone(phone: str) -> None:
    client, svc, headers = _admin_client()
    svc._repo.get_customer_by_id = MagicMock(return_value=_row())
    svc._repo.flush = MagicMock()
    with client:
        response = client.patch(
            f"/api/v1/salons/{SALON_ID}/customers/{CUSTOMER_ID}",
            headers=headers,
            json={"phone": phone},
        )
    assert response.status_code == 422
    svc._repo.flush.assert_not_called()
