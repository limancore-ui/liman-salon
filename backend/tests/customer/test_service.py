from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.customer import Customer
from app.services.customer.errors import CustomerConflictError, CustomerValidationError
from app.services.customer.service import (
    CustomerCreateData,
    CustomerService,
    CustomerUpdateData,
    PublicCustomerResolveData,
)
from app.services.customer.types import CustomerResolveResult

SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _svc() -> CustomerService:
    return CustomerService(MagicMock())


def test_resolve_returns_existing_by_phone_without_update() -> None:
    svc = _svc()
    existing = Customer(
        id=CUSTOMER_ID,
        salon_id=SALON_ID,
        full_name="Original",
        phone="+77001112233",
    )
    svc._repo.get_customer_by_phone = MagicMock(return_value=existing)
    svc._repo.add_customer = MagicMock()

    result = svc.resolve_public_customer(
        salon_id=SALON_ID,
        data=PublicCustomerResolveData(full_name="New Name", phone="+77001112233"),
    )

    assert result == CustomerResolveResult(customer_id=CUSTOMER_ID, created=False)
    svc._repo.add_customer.assert_not_called()


def test_resolve_creates_with_defaults() -> None:
    svc = _svc()
    svc._repo.get_customer_by_phone = MagicMock(return_value=None)

    def _add(customer: Customer) -> Customer:
        customer.id = CUSTOMER_ID
        return customer

    svc._repo.add_customer = MagicMock(side_effect=_add)

    result = svc.resolve_public_customer(
        salon_id=SALON_ID,
        data=PublicCustomerResolveData(
            full_name="Walk-in",
            phone="+77005556677",
            email="w@example.com",
        ),
    )

    assert result.created is True
    added = svc._repo.add_customer.call_args[0][0]
    assert added.notes is None
    assert added.marketing_opt_in is False
    assert added.whatsapp_opt_in is False
    assert added.user_id is None


def test_resolve_integrity_error_becomes_conflict() -> None:
    svc = _svc()
    svc._repo.get_customer_by_phone = MagicMock(return_value=None)
    svc._repo.add_customer = MagicMock(side_effect=IntegrityError("insert", {}, Exception()))
    with pytest.raises(CustomerConflictError):
        svc.resolve_public_customer(
            salon_id=SALON_ID,
            data=PublicCustomerResolveData(full_name="A", phone="+7700"),
        )


def test_whatsapp_opt_in_timestamps_on_create() -> None:
    svc = _svc()
    svc._repo.add_customer = MagicMock(side_effect=lambda c: c)

    created = svc.create_customer(
        salon_id=SALON_ID,
        data=CustomerCreateData(full_name="A", whatsapp_opt_in=True),
        clock=lambda: NOW,
    )
    assert created.whatsapp_opt_in_at == NOW


def test_whatsapp_opt_in_toggle_on_update() -> None:
    svc = _svc()
    row = Customer(
        id=CUSTOMER_ID,
        salon_id=SALON_ID,
        full_name="A",
        whatsapp_opt_in=False,
        whatsapp_opt_in_at=None,
    )
    svc._repo.get_customer_by_id = MagicMock(return_value=row)
    svc._repo.flush = MagicMock()

    updated = svc.update_customer(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        data=CustomerUpdateData(whatsapp_opt_in=True),
        clock=lambda: NOW,
    )
    assert updated.whatsapp_opt_in_at == NOW

    row.whatsapp_opt_in = True
    row.whatsapp_opt_in_at = NOW
    cleared = svc.update_customer(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        data=CustomerUpdateData(whatsapp_opt_in=False),
        clock=lambda: NOW,
    )
    assert cleared.whatsapp_opt_in_at is None


def test_blank_phone_on_resolve_raises() -> None:
    svc = _svc()
    with pytest.raises(CustomerValidationError):
        svc.resolve_public_customer(
            salon_id=SALON_ID,
            data=PublicCustomerResolveData(full_name="A", phone="   "),
        )
