"""Unit tests: one shared schedule lock acquire per booking mutation path."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.types import ServiceForAvailability
from app.services.booking.manage_token import hash_manage_token
from app.services.booking.service import BookingService
from app.services.booking.types import CreateBookingResult
from app.services.public_booking.service import PublicBookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()
AS_OF = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
REQUESTED = datetime(2026, 6, 2, 10, 0, tzinfo=UTC)
NEW_START = datetime(2026, 6, 3, 14, 0, tzinfo=UTC)
RAW_TOKEN = "schedule-gate-wiring-token"
PEPPER = get_settings().booking_manage_token_pepper

_LOCK_TARGET = "app.services.booking.service.acquire_schedule_lock_shared"
_PUBLIC_LOCK_TARGET = "app.services.public_booking.service.acquire_schedule_lock_shared"


def _booking_service_with_mocks() -> tuple[BookingService, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    availability = MagicMock()
    svc._repo = repo
    svc._availability = availability
    repo.get_salon_currency.return_value = "KZT"
    repo.get_salon_settings.return_value = {}
    customer = Customer(salon_id=SALON_ID, full_name="Pat")
    customer.id = CUSTOMER_ID
    repo.get_customer.return_value = customer
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
    repo.expire_stale_pending_holds.return_value = 0
    availability.is_occupied_interval_available.return_value = True

    def _add(booking: Booking) -> Booking:
        booking.id = uuid.uuid4()
        return booking

    repo.add_booking.side_effect = _add
    return svc, session


def _reschedule_booking() -> Booking:
    booking = Booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        starts_at=REQUESTED,
        ends_at=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
        status="confirmed",
        source="public",
        price_cents=1000,
        currency_code="KZT",
        duration_minutes=60,
        manage_token_hash=hash_manage_token(RAW_TOKEN, pepper=PEPPER),
    )
    booking.id = BOOKING_ID
    return booking


def test_create_booking_acquires_shared_lock_once() -> None:
    svc, session = _booking_service_with_mocks()
    with patch(_LOCK_TARGET) as acquire:
        svc.create_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            requested_service_start=REQUESTED,
            source="admin",
            status="confirmed",
            as_of=AS_OF,
        )
    acquire.assert_called_once_with(session, SALON_ID)


def test_create_booking_skips_lock_when_gate_already_held() -> None:
    svc, _session = _booking_service_with_mocks()
    with patch(_LOCK_TARGET) as acquire:
        svc.create_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            requested_service_start=REQUESTED,
            source="public",
            status="pending",
            as_of=AS_OF,
            expires_at=AS_OF + timedelta(hours=1),
            schedule_gate_shared_held=True,
        )
    acquire.assert_not_called()


def test_reschedule_booking_acquires_shared_lock_once() -> None:
    booking = _reschedule_booking()
    svc, session = _booking_service_with_mocks()
    svc._repo.get_booking.return_value = booking
    with patch(_LOCK_TARGET) as acquire:
        svc.reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            token=RAW_TOKEN,
            new_staff_id=STAFF_ID,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )
    acquire.assert_called_once_with(session, SALON_ID)


def test_admin_reschedule_booking_acquires_shared_lock_once() -> None:
    booking = _reschedule_booking()
    svc, session = _booking_service_with_mocks()
    svc._repo.get_booking.return_value = booking
    with patch(_LOCK_TARGET) as acquire:
        svc.admin_reschedule_booking(
            salon_id=SALON_ID,
            booking_id=BOOKING_ID,
            new_staff_id=STAFF_ID,
            new_service_start=NEW_START,
            as_of=AS_OF,
        )
    acquire.assert_called_once_with(session, SALON_ID)


def test_public_booking_acquires_shared_lock_once_and_passes_held_flag() -> None:
    session = MagicMock()
    svc = PublicBookingService(session, booking_manage_token_pepper=PEPPER)
    svc._booking._repo = MagicMock()
    svc._booking._repo.get_salon_settings.return_value = {}
    service_row = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=True,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    with (
        patch.object(
            svc._availability_repo,
            "get_service_for_availability",
            return_value=service_row,
        ),
        patch.object(svc._availability, "is_service_slot_available", return_value=True),
        patch.object(
            svc._booking,
            "create_booking",
            return_value=CreateBookingResult(
                booking_id=uuid.uuid4(),
                starts_at=REQUESTED,
                ends_at=datetime(2026, 6, 2, 11, 0, tzinfo=UTC),
                status="pending",
            ),
        ) as create,
        patch(_PUBLIC_LOCK_TARGET) as acquire,
    ):
        svc.create_public_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            service_start=REQUESTED,
            as_of=AS_OF,
        )
    acquire.assert_called_once_with(session, SALON_ID)
    assert create.call_args.kwargs["schedule_gate_shared_held"] is True


def test_public_booking_missing_service_does_not_acquire_lock() -> None:
    session = MagicMock()
    svc = PublicBookingService(session, booking_manage_token_pepper=PEPPER)
    svc._booking._repo = MagicMock()
    svc._booking._repo.get_salon_settings.return_value = {}
    with (
        patch.object(
            svc._availability_repo,
            "get_service_for_availability",
            return_value=None,
        ),
        patch(_PUBLIC_LOCK_TARGET) as acquire,
    ):
        with pytest.raises(ServiceNotFoundError):
            svc.create_public_booking(
                salon_id=SALON_ID,
                customer_id=CUSTOMER_ID,
                staff_id=STAFF_ID,
                service_id=SERVICE_ID,
                service_start=REQUESTED,
                as_of=AS_OF,
            )
    acquire.assert_not_called()
