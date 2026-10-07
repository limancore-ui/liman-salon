from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.customer.errors import CustomerValidationError
from app.services.customer.phone import normalize_kg_phone
from app.services.customer.service import (
    CustomerCreateData,
    CustomerService,
    CustomerUpdateData,
    PublicCustomerResolveData,
)

SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
CANONICAL = "+996555123456"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("555123456", CANONICAL),
        ("+996555123456", CANONICAL),
        ("  555123456  ", CANONICAL),
        ("  +996555123456\n", CANONICAL),
        ("000000000", "+996000000000"),
    ],
)
def test_normalize_accepts_local_and_canonical(raw: str, expected: str) -> None:
    assert normalize_kg_phone(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "55512345",  # 8 digits
        "5551234567",  # 10 digits
        "+99655512345",  # canonical, too short
        "+9965551234567",  # canonical, too long
        "+77001234567",  # Kazakhstan / Russia
        "+998901234567",  # Uzbekistan
        "996555123456",  # country code without plus
        "+996 555 123 456",  # inner spaces
        "555-123-456",  # separators
        "(555)123456",
        "55512345a",  # alpha
        "abcdefghi",
        "+996abcdefghi",
        "++996555123456",
        "+٩٩٦٥٥٥١٢٣٤٥٦",  # non-ASCII digits
        "٥٥٥١٢٣٤٥٦",
    ],
)
def test_normalize_rejects_invalid(raw: str) -> None:
    with pytest.raises(CustomerValidationError):
        normalize_kg_phone(raw)


def _svc() -> CustomerService:
    return CustomerService(MagicMock())


def test_resolve_stores_canonical_from_local_digits() -> None:
    svc = _svc()
    svc._repo.get_customer_by_phone = MagicMock(return_value=None)
    svc._repo.add_customer = MagicMock(side_effect=lambda c: c)

    svc.resolve_public_customer(
        salon_id=SALON_ID,
        data=PublicCustomerResolveData(full_name="Jane", phone="555123456"),
    )

    svc._repo.get_customer_by_phone.assert_called_once_with(
        salon_id=SALON_ID, phone=CANONICAL
    )
    assert svc._repo.add_customer.call_args[0][0].phone == CANONICAL


@pytest.mark.parametrize("raw", ["+77001234567", "+998901234567", "12345", "abc"])
def test_resolve_rejects_invalid_without_repo_access(raw: str) -> None:
    svc = _svc()
    svc._repo.get_customer_by_phone = MagicMock()
    svc._repo.add_customer = MagicMock()

    with pytest.raises(CustomerValidationError):
        svc.resolve_public_customer(
            salon_id=SALON_ID,
            data=PublicCustomerResolveData(full_name="Jane", phone=raw),
        )

    svc._repo.get_customer_by_phone.assert_not_called()
    svc._repo.add_customer.assert_not_called()


def test_lookup_uses_canonical_and_stays_salon_scoped() -> None:
    svc = _svc()
    svc._repo.get_customer_by_phone = MagicMock(return_value=None)

    svc.lookup_public_customer(salon_id=SALON_ID, phone="555123456")

    svc._repo.get_customer_by_phone.assert_called_once_with(
        salon_id=SALON_ID, phone=CANONICAL
    )


def test_lookup_rejects_invalid() -> None:
    svc = _svc()
    svc._repo.get_customer_by_phone = MagicMock()
    with pytest.raises(CustomerValidationError):
        svc.lookup_public_customer(salon_id=SALON_ID, phone="+77001234567")
    svc._repo.get_customer_by_phone.assert_not_called()


def test_admin_create_normalizes_phone() -> None:
    svc = _svc()
    svc._repo.add_customer = MagicMock(side_effect=lambda c: c)

    created = svc.create_customer(
        salon_id=SALON_ID,
        data=CustomerCreateData(full_name="A", phone="555123456"),
        clock=lambda: NOW,
    )

    assert created.phone == CANONICAL


def test_admin_create_without_phone_stays_none() -> None:
    svc = _svc()
    svc._repo.add_customer = MagicMock(side_effect=lambda c: c)

    created = svc.create_customer(
        salon_id=SALON_ID,
        data=CustomerCreateData(full_name="A"),
        clock=lambda: NOW,
    )

    assert created.phone is None


def test_admin_create_rejects_invalid_phone() -> None:
    svc = _svc()
    svc._repo.add_customer = MagicMock()
    with pytest.raises(CustomerValidationError):
        svc.create_customer(
            salon_id=SALON_ID,
            data=CustomerCreateData(full_name="A", phone="+77001234567"),
            clock=lambda: NOW,
        )
    svc._repo.add_customer.assert_not_called()


def _row(**kwargs: object) -> SimpleNamespace:
    base = {
        "id": CUSTOMER_ID,
        "salon_id": SALON_ID,
        "full_name": "Old",
        "phone": "+996700000000",
        "whatsapp_opt_in": False,
        "whatsapp_opt_in_at": None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_admin_update_normalizes_phone() -> None:
    svc = _svc()
    row = _row()
    svc._repo.get_customer_by_id = MagicMock(return_value=row)
    svc._repo.flush = MagicMock()

    svc.update_customer(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        data=CustomerUpdateData(phone="555123456"),
        clock=lambda: NOW,
    )

    assert row.phone == CANONICAL


def test_admin_update_invalid_phone_leaves_row_untouched() -> None:
    svc = _svc()
    row = _row()
    svc._repo.get_customer_by_id = MagicMock(return_value=row)
    svc._repo.flush = MagicMock()

    with pytest.raises(CustomerValidationError):
        svc.update_customer(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            data=CustomerUpdateData(full_name="New Name", phone="+998901234567"),
            clock=lambda: NOW,
        )

    assert row.phone == "+996700000000"
    assert row.full_name == "Old"
    svc._repo.flush.assert_not_called()


def test_admin_update_without_phone_keeps_existing() -> None:
    svc = _svc()
    row = _row()
    svc._repo.get_customer_by_id = MagicMock(return_value=row)
    svc._repo.flush = MagicMock()

    svc.update_customer(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        data=CustomerUpdateData(full_name="Renamed"),
        clock=lambda: NOW,
    )

    assert row.phone == "+996700000000"
    assert row.full_name == "Renamed"
