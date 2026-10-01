from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest

from app.services.salon_settings import SalonSettingsError
from .test_service import (
    AS_OF,
    CUSTOMER_ID,
    REQUESTED,
    SALON_ID,
    SERVICE_ID,
    STAFF_ID,
    _booking_service_with_mocks,
)


def test_admin_pending_uses_salon_hold_override() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.get_salon_settings.return_value = {
        "v": 1,
        "booking": {"public_hold_seconds": 1200},
    }

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
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.expires_at == AS_OF + timedelta(seconds=1200)


def test_admin_pending_without_override_uses_app_setting() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.get_salon_settings.return_value = {}

    with patch("app.services.booking.service.get_settings") as mock_settings:
        mock_settings.return_value.public_booking_hold_seconds = 1800
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
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.expires_at == AS_OF + timedelta(seconds=1800)


def test_confirmed_admin_does_not_set_expires_at() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.get_salon_settings.return_value = {
        "v": 1,
        "booking": {"public_hold_seconds": 1200},
    }

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
    booking_arg = repo.add_booking.call_args[0][0]
    assert booking_arg.expires_at is None


def test_malformed_salon_settings_rejected_on_hold_resolve() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.get_salon_settings.return_value = {
        "v": 1,
        "booking": {"public_hold_seconds": -1},
    }
    with pytest.raises(SalonSettingsError):
        svc.resolve_pending_hold_seconds(SALON_ID)


def test_expire_all_stale_pending_holds_does_not_read_salon_settings() -> None:
    svc, repo, _ = _booking_service_with_mocks()
    repo.expire_all_stale_pending_holds.return_value = 2

    assert svc.expire_all_stale_pending_holds(as_of=AS_OF) == 2
    repo.expire_all_stale_pending_holds.assert_called_once_with(as_of=AS_OF)
    repo.get_salon_settings.assert_not_called()
