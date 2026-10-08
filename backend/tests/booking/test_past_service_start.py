from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.booking.errors import BookingValidationError
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
AS_OF = datetime(2025, 6, 2, 16, 55, tzinfo=UTC)
PAST_START = datetime(2025, 6, 2, 16, 30, tzinfo=UTC)


def _booking_service_with_mocks() -> BookingService:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    availability = MagicMock()
    svc._repo = repo
    svc._availability = availability
    repo.get_salon_currency.return_value = "KZT"
    repo.get_salon_settings.return_value = {}
    repo.get_customer.return_value = Customer(salon_id=SALON_ID, full_name="Pat")
    staff = Staff(
        salon_id=SALON_ID,
        display_name="Alex",
        is_active=True,
        is_bookable=True,
    )
    staff.id = STAFF_ID
    repo.get_staff.return_value = staff
    service = Service(
        salon_id=SALON_ID,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=5000,
        is_active=True,
    )
    service.id = SERVICE_ID
    repo.get_service.return_value = service
    repo.staff_performs_service.return_value = True
    return svc


def test_create_booking_rejects_past_service_start() -> None:
    svc = _booking_service_with_mocks()
    with pytest.raises(BookingValidationError, match="past"):
        svc.create_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            requested_service_start=PAST_START,
            source="public",
            status="pending",
            as_of=AS_OF,
            expires_at=datetime(2025, 6, 2, 17, 55, tzinfo=UTC),
        )


def test_reschedule_rejects_past_service_start() -> None:
    svc = _booking_service_with_mocks()
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        starts_at=datetime(2025, 6, 3, 10, 0, tzinfo=UTC),
        ends_at=datetime(2025, 6, 3, 11, 0, tzinfo=UTC),
        status="confirmed",
        source="public",
        price_cents=1000,
        currency_code="KZT",
        duration_minutes=60,
    )
    booking.id = uuid.uuid4()
    with pytest.raises(BookingValidationError, match="past"):
        svc._reschedule_booking_loaded(
            booking,
            salon_id=SALON_ID,
            new_staff_id=STAFF_ID,
            new_service_start=PAST_START,
            as_of=AS_OF,
        )
