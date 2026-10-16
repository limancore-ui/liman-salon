from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.availability.errors import ServiceNotFoundError
from app.services.availability.types import ServiceForAvailability
from app.services.booking.errors import SlotNotAvailableError
from app.services.booking.manage_token import hash_manage_token, verify_manage_token
from app.services.booking.types import CreateBookingResult
from app.services.public_booking.service import PublicBookingService

UTC = timezone.utc
SALON_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_ID = uuid.uuid4()
SERVICE_ID = uuid.uuid4()
AS_OF = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
SERVICE_START = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
TEST_PEPPER = "unit-test-booking-manage-token-pepper"


def _svc(session: MagicMock | None = None) -> PublicBookingService:
    session = session or MagicMock()
    svc = PublicBookingService(
        session,
        booking_manage_token_pepper=TEST_PEPPER,
    )
    svc._booking._repo = MagicMock()
    svc._booking._repo.get_salon_settings.return_value = {}
    return svc


def test_create_public_booking_precheck_then_delegates() -> None:
    svc = _svc()
    service_row = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=True,
        duration_minutes=60,
        buffer_before_minutes=15,
        buffer_after_minutes=15,
    )
    booking_id = uuid.uuid4()

    with (
        patch.object(svc._availability_repo, "get_service_for_availability", return_value=service_row),
        patch.object(svc._availability, "is_service_slot_available", return_value=True) as precheck,
        patch.object(
            svc._booking,
            "create_booking",
            return_value=CreateBookingResult(
                booking_id=booking_id,
                starts_at=SERVICE_START - timedelta(minutes=15),
                ends_at=SERVICE_START + timedelta(minutes=75),
                status="confirmed",
            ),
        ) as create,
    ):
        result = svc.create_public_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            service_start=SERVICE_START,
            as_of=AS_OF,
        )

    precheck.assert_called_once()
    create.assert_called_once()
    kwargs = create.call_args.kwargs
    assert kwargs["source"] == "public"
    assert kwargs["status"] == "confirmed"
    assert kwargs["requested_service_start"] == SERVICE_START
    assert kwargs["expires_at"] is None
    assert kwargs["as_of"] == AS_OF
    assert kwargs["manage_token_hash"] is not None
    assert kwargs["manage_token_hash"] != result.manage_token

    assert result.booking_id == booking_id
    assert result.manage_token
    assert verify_manage_token(
        result.manage_token,
        kwargs["manage_token_hash"],
        pepper=TEST_PEPPER,
    )
    assert kwargs["manage_token_hash"] == hash_manage_token(
        result.manage_token,
        pepper=TEST_PEPPER,
    )
    assert result.service_start == SERVICE_START
    assert result.service_end == SERVICE_START + timedelta(minutes=60)
    assert result.hold_expires_at is None
    assert result.status == "confirmed"


def test_create_public_booking_ignores_salon_hold_override() -> None:
    svc = _svc()
    svc._booking._repo.get_salon_settings.return_value = {
        "v": 1,
        "booking": {"public_hold_seconds": 1200},
    }
    service_row = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=True,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    with (
        patch.object(svc._availability_repo, "get_service_for_availability", return_value=service_row),
        patch.object(svc._availability, "is_service_slot_available", return_value=True),
        patch.object(
            svc._booking,
            "create_booking",
            return_value=CreateBookingResult(
                booking_id=uuid.uuid4(),
                starts_at=SERVICE_START,
                ends_at=SERVICE_START + timedelta(minutes=60),
                status="confirmed",
            ),
        ) as create,
    ):
        result = svc.create_public_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            service_start=SERVICE_START,
            as_of=AS_OF,
        )

    assert create.call_args.kwargs["status"] == "confirmed"
    assert create.call_args.kwargs["expires_at"] is None
    assert result.hold_expires_at is None


def test_public_booking_uses_injected_notification_service() -> None:
    session = MagicMock()
    notifications = MagicMock()
    svc = PublicBookingService(
        session,
        booking_manage_token_pepper=TEST_PEPPER,
        notifications=notifications,
    )
    assert svc._booking._notifications is notifications


def test_confirmed_public_create_does_not_enqueue_admin_bell() -> None:
    admin_notifications = MagicMock()
    svc = PublicBookingService(
        MagicMock(),
        booking_manage_token_pepper=TEST_PEPPER,
        admin_notifications=admin_notifications,
    )
    svc._booking._repo = MagicMock()
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
                starts_at=SERVICE_START,
                ends_at=SERVICE_START + timedelta(minutes=60),
                status="confirmed",
            ),
        ),
    ):
        svc.create_public_booking(
            salon_id=SALON_ID,
            customer_id=CUSTOMER_ID,
            staff_id=STAFF_ID,
            service_id=SERVICE_ID,
            service_start=SERVICE_START,
            as_of=AS_OF,
        )
    admin_notifications.enqueue_public_booking_pending.assert_not_called()


def test_create_public_booking_missing_service_404() -> None:
    svc = _svc()
    with patch.object(
        svc._availability_repo, "get_service_for_availability", return_value=None
    ):
        with pytest.raises(ServiceNotFoundError):
            svc.create_public_booking(
                salon_id=SALON_ID,
                customer_id=CUSTOMER_ID,
                staff_id=STAFF_ID,
                service_id=SERVICE_ID,
                service_start=SERVICE_START,
                as_of=AS_OF,
            )


def test_create_public_booking_precheck_unavailable_409() -> None:
    svc = _svc()
    service_row = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=True,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    with (
        patch.object(svc._availability_repo, "get_service_for_availability", return_value=service_row),
        patch.object(svc._availability, "is_service_slot_available", return_value=False),
        patch.object(svc._booking, "create_booking") as create,
    ):
        with pytest.raises(SlotNotAvailableError):
            svc.create_public_booking(
                salon_id=SALON_ID,
                customer_id=CUSTOMER_ID,
                staff_id=STAFF_ID,
                service_id=SERVICE_ID,
                service_start=SERVICE_START,
                as_of=AS_OF,
            )
    create.assert_not_called()


def test_create_public_booking_inactive_skips_precheck() -> None:
    svc = _svc()
    service_row = ServiceForAvailability(
        id=SERVICE_ID,
        is_active=False,
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
    )
    with (
        patch.object(svc._availability_repo, "get_service_for_availability", return_value=service_row),
        patch.object(svc._availability, "is_service_slot_available") as precheck,
        patch.object(
            svc._booking,
            "create_booking",
            side_effect=Exception("should reach booking validation"),
        ) as create,
    ):
        with pytest.raises(Exception, match="should reach booking validation"):
            svc.create_public_booking(
                salon_id=SALON_ID,
                customer_id=CUSTOMER_ID,
                staff_id=STAFF_ID,
                service_id=SERVICE_ID,
                service_start=SERVICE_START,
                as_of=AS_OF,
            )
    precheck.assert_not_called()
    create.assert_called_once()
