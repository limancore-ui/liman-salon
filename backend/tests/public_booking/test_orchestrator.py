from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.services.customer.service import CustomerService, PublicCustomerResolveData
from app.services.customer.types import CustomerResolveResult
from app.services.public_booking.orchestrator import PublicBookingOrchestrator
from app.services.public_booking.types import PublicBookingResult
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.types import PublicSalonEntry

UTC = timezone.utc
SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
AS_OF = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
SERVICE_START = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
SERVICE_END = datetime(2026, 9, 25, 11, 0, tzinfo=UTC)
HOLD = AS_OF + timedelta(seconds=900)
MANAGE_TOKEN = "mock-manage-token-for-tests"


def _orchestrator() -> tuple[PublicBookingOrchestrator, MagicMock, MagicMock, MagicMock]:
    salon_public = MagicMock()
    customer = MagicMock(spec=CustomerService)
    public_booking = MagicMock()
    return (
        PublicBookingOrchestrator(salon_public, customer, public_booking),
        salon_public,
        customer,
        public_booking,
    )


def test_orchestrator_resolves_salon_then_customer_then_booking() -> None:
    orch, salon_public, customer, public_booking = _orchestrator()
    salon_public.resolve_public_salon_by_slug.return_value = PublicSalonEntry(
        salon_id=SALON_ID,
        slug="liman-demo",
        name="Demo",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )
    customer.resolve_public_customer.return_value = CustomerResolveResult(
        customer_id=CUSTOMER_ID,
        created=True,
    )
    public_booking.create_public_booking.return_value = PublicBookingResult(
        booking_id=BOOKING_ID,
        status="pending",
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        service_end=SERVICE_END,
        hold_expires_at=HOLD,
        manage_token=MANAGE_TOKEN,
    )

    result = orch.create_public_booking_by_slug(
        slug="liman-demo",
        full_name="Jane",
        phone="+77001234567",
        email=None,
        service_id=SERVICE_ID,
        staff_id=STAFF_ID,
        service_start=SERVICE_START,
        as_of=AS_OF,
    )

    salon_public.resolve_public_salon_by_slug.assert_called_once_with("liman-demo")
    customer.resolve_public_customer.assert_called_once_with(
        salon_id=SALON_ID,
        data=PublicCustomerResolveData(
            full_name="Jane",
            phone="+77001234567",
            email=None,
        ),
    )
    public_booking.create_public_booking.assert_called_once()
    kwargs = public_booking.create_public_booking.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["customer_id"] == CUSTOMER_ID
    assert kwargs["as_of"] == AS_OF

    assert result.salon_id == SALON_ID
    assert result.customer_id == CUSTOMER_ID
    assert result.booking_id == BOOKING_ID
    assert result.service_start == SERVICE_START
    assert result.service_end == SERVICE_END
    assert result.hold_expires_at == HOLD
    assert result.manage_token == MANAGE_TOKEN


def test_orchestrator_unknown_slug_propagates_not_found() -> None:
    orch, salon_public, customer, public_booking = _orchestrator()
    salon_public.resolve_public_salon_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )

    with pytest.raises(PublicSalonNotFoundError):
        orch.create_public_booking_by_slug(
            slug="missing",
            full_name="Jane",
            phone="+77001234567",
            email=None,
            service_id=SERVICE_ID,
            staff_id=STAFF_ID,
            service_start=SERVICE_START,
            as_of=AS_OF,
        )

    customer.resolve_public_customer.assert_not_called()
    public_booking.create_public_booking.assert_not_called()
