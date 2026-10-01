from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from sqlalchemy.exc import IntegrityError

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.booking.errors import (
    BookingNotFoundError,
    BookingOverlapError,
    BookingValidationError,
    SlotNotAvailableError,
)
from app.services.booking.service import BookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
AS_OF = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
REQUESTED = datetime(2025, 6, 2, 10, 0, tzinfo=UTC)


def _active_staff() -> Staff:
    staff = Staff(
        salon_id=SALON_ID,
        display_name="Alex",
        is_active=True,
        is_bookable=True,
    )
    staff.id = STAFF_ID
    return staff


def _active_service() -> Service:
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
    return service


def _customer() -> Customer:
    customer = Customer(salon_id=SALON_ID, full_name="Pat")
    customer.id = CUSTOMER_ID
    return customer


def _booking_service_with_mocks() -> tuple[BookingService, MagicMock, MagicMock]:
    session = MagicMock()
    svc = BookingService(session)
    repo = MagicMock()
    availability = MagicMock()
    svc._repo = repo
    svc._availability = availability
    repo.get_salon_currency.return_value = "KZT"
    repo.get_salon_settings.return_value = {}
    repo.get_customer.return_value = _customer()
    repo.get_staff.return_value = _active_staff()
    repo.get_service.return_value = _active_service()
    repo.staff_performs_service.return_value = True
    repo.expire_stale_pending_holds.return_value = 0
    availability.is_occupied_interval_available.return_value = True

    def _add(booking: Booking) -> Booking:
        booking.id = uuid.uuid4()
        return booking

    repo.add_booking.side_effect = _add
    return svc, repo, availability


def test_create_confirmed_persists_occupied_and_snapshots() -> None:
    svc, repo, availability = _booking_service_with_mocks()
    result = svc.create_booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        requested_service_start=REQUESTED,
        source="admin",
        status="confirmed",
        as_of=AS_OF,
        customer_notes="hello",
    )
    assert result.status == "confirmed"
    assert result.starts_at == REQUESTED
    assert result.ends_at == datetime(2025, 6, 2, 11, 0, tzinfo=UTC)
    repo.expire_stale_pending_holds.assert_called_once()
    availability.is_occupied_interval_available.assert_called_once()
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.price_cents == 5000
    assert booking_arg.currency_code == "KZT"
    assert booking_arg.duration_minutes == 60
    assert booking_arg.confirmed_at == AS_OF
    assert booking_arg.expires_at is None
    assert booking_arg.customer_notes == "hello"


def test_public_pending_requires_expires_at_after_as_of() -> None:
    svc, _, _ = _booking_service_with_mocks()
    with pytest.raises(BookingValidationError):
        svc.create_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            requested_service_start=REQUESTED,
            source="public",
            status="pending",
            as_of=AS_OF,
            expires_at=None,
        )
    with pytest.raises(BookingValidationError):
        svc.create_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            requested_service_start=REQUESTED,
            source="public",
            status="pending",
            as_of=AS_OF,
            expires_at=AS_OF,
        )


def test_confirmed_rejects_expires_at() -> None:
    svc, _, _ = _booking_service_with_mocks()
    with pytest.raises(BookingValidationError):
        svc.create_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            requested_service_start=REQUESTED,
            source="admin",
            status="confirmed",
            as_of=AS_OF,
            expires_at=datetime(2025, 6, 2, 13, 0, tzinfo=UTC),
        )


def test_expire_stale_pending_called_with_occupied_window() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    svc._repo.get_service.return_value = Service(
        salon_id=SALON_ID,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=15,
        buffer_after_minutes=10,
        price_cents=100,
        is_active=True,
    )
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
    kwargs = repo.expire_stale_pending_holds.call_args.kwargs
    assert kwargs["salon_id"] == SALON_ID
    assert kwargs["staff_id"] == STAFF_ID
    assert kwargs["as_of"] == AS_OF
    assert kwargs["window_start"] == datetime(2025, 6, 2, 9, 45, tzinfo=UTC)
    assert kwargs["window_end"] == datetime(2025, 6, 2, 11, 10, tzinfo=UTC)


def test_tenant_isolation_unknown_staff() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.get_staff.return_value = None
    with pytest.raises(BookingNotFoundError):
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


def test_inactive_service_rejected() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    inactive = _active_service()
    inactive.is_active = False
    repo.get_service.return_value = inactive
    with pytest.raises(BookingValidationError):
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


def test_staff_service_link_required() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.staff_performs_service.return_value = False
    with pytest.raises(BookingValidationError):
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


def test_slot_not_available() -> None:
    svc, _, availability = _booking_service_with_mocks()
    availability.is_occupied_interval_available.return_value = False
    with pytest.raises(SlotNotAvailableError):
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


def test_integrity_error_becomes_overlap_error() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.add_booking.side_effect = IntegrityError("insert", {}, Exception("overlap"))
    with pytest.raises(BookingOverlapError):
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


def test_create_booking_does_not_open_nested_transaction() -> None:
    svc, repo, availability = _booking_service_with_mocks()
    session = svc._session
    result = svc.create_booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        requested_service_start=REQUESTED,
        source="admin",
        status="confirmed",
        as_of=AS_OF,
    )
    assert result.status == "confirmed"
    session.begin.assert_not_called()


def test_public_pending_success_sets_expires_at() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    expires = datetime(2025, 6, 1, 13, 0, tzinfo=UTC)
    svc.create_booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        requested_service_start=REQUESTED,
        source="public",
        status="pending",
        as_of=AS_OF,
        expires_at=expires,
    )
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.status == "pending"
    assert booking_arg.expires_at == expires
    assert booking_arg.confirmed_at is None


def test_admin_pending_server_generates_expires_at() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    client_expires = datetime(2099, 1, 1, 0, 0, tzinfo=UTC)
    svc.create_booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        requested_service_start=REQUESTED,
        source="admin",
        status="pending",
        as_of=AS_OF,
        expires_at=client_expires,
    )
    hold_seconds = get_settings().public_booking_hold_seconds
    expected = AS_OF + timedelta(seconds=hold_seconds)
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.status == "pending"
    assert booking_arg.expires_at == expected
    assert booking_arg.expires_at != client_expires


def test_admin_pending_without_client_expires_still_gets_hold() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    svc.create_booking(
        salon_id=SALON_ID,
        customer_id=CUSTOMER_ID,
        staff_id=STAFF_ID,
        service_id=SERVICE_ID,
        requested_service_start=REQUESTED,
        source="admin",
        status="pending",
        as_of=AS_OF,
    )
    hold_seconds = get_settings().public_booking_hold_seconds
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.expires_at == AS_OF + timedelta(seconds=hold_seconds)
