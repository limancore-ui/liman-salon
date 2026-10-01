from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.services.salon_settings.errors import SalonSettingsError, SalonSettingsNotFoundError
from app.services.salon_settings.service import (
    SalonBookingPatchData,
    SalonSettingsPatchData,
    SalonSettingsService,
    merge_settings_patch,
    normalize_stored_settings,
    validate_stored_settings,
)


def test_merge_set_public_hold_seconds() -> None:
    merged = merge_settings_patch(
        {},
        SalonSettingsPatchData(
            booking_set=True,
            booking=SalonBookingPatchData(public_hold_seconds=1200),
        ),
    )
    assert merged == {"v": 1, "booking": {"public_hold_seconds": 1200}}
    assert validate_stored_settings(merged) == merged


def test_merge_clear_booking_null() -> None:
    current = {"v": 1, "booking": {"public_hold_seconds": 900}}
    merged = merge_settings_patch(
        current,
        SalonSettingsPatchData(booking_set=True, booking=None),
    )
    assert merged == {}
    assert validate_stored_settings(merged) == {}


def test_merge_no_booking_field_leaves_current() -> None:
    current = {"v": 1, "booking": {"public_hold_seconds": 900}}
    merged = merge_settings_patch(
        current,
        SalonSettingsPatchData(booking_set=False),
    )
    assert merged == current


def test_normalize_empty_without_booking() -> None:
    assert normalize_stored_settings({"v": 1}) == {}


def test_validate_rejects_out_of_range() -> None:
    with pytest.raises(SalonSettingsError, match="invalid salon settings"):
        validate_stored_settings({"v": 1, "booking": {"public_hold_seconds": 30}})


def test_service_get_view_platform_default() -> None:
    repo = MagicMock()
    repo.salon_exists.return_value = True
    repo.get_settings.return_value = {}
    svc = SalonSettingsService(MagicMock(), app_hold_seconds=900)
    svc._repo = repo
    view = svc.get_settings(salon_id=uuid.uuid4())
    assert view.v == 1
    assert view.public_hold_seconds is None


def test_service_get_view_with_override() -> None:
    repo = MagicMock()
    repo.salon_exists.return_value = True
    repo.get_settings.return_value = {
        "v": 1,
        "booking": {"public_hold_seconds": 1200},
    }
    svc = SalonSettingsService(MagicMock(), app_hold_seconds=900)
    svc._repo = repo
    view = svc.get_settings(salon_id=uuid.uuid4())
    assert view.public_hold_seconds == 1200


def test_service_salon_missing_404() -> None:
    repo = MagicMock()
    repo.salon_exists.return_value = False
    svc = SalonSettingsService(MagicMock(), app_hold_seconds=900)
    svc._repo = repo
    with pytest.raises(SalonSettingsNotFoundError):
        svc.get_settings(salon_id=uuid.uuid4())
