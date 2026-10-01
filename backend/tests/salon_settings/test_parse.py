from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.salon_settings import SalonSettingsError, resolve_public_booking_hold_seconds


def test_resolve_hold_salon_override_1200() -> None:
    settings = {"v": 1, "booking": {"public_hold_seconds": 1200}}
    assert (
        resolve_public_booking_hold_seconds(settings, app_hold_seconds=900)
        == 1200
    )


def test_resolve_hold_falls_back_to_app_setting() -> None:
    assert resolve_public_booking_hold_seconds({}, app_hold_seconds=1800) == 1800


def test_resolve_hold_empty_json_uses_app_default() -> None:
    app_default = get_settings().public_booking_hold_seconds
    assert (
        resolve_public_booking_hold_seconds({}, app_hold_seconds=app_default)
        == app_default
    )


def test_invalid_hold_value_rejected() -> None:
    settings = {"v": 1, "booking": {"public_hold_seconds": 30}}
    with pytest.raises(SalonSettingsError, match="invalid salon settings"):
        resolve_public_booking_hold_seconds(settings, app_hold_seconds=900)


def test_unknown_top_level_key_rejected() -> None:
    settings = {"v": 1, "unexpected": True}
    with pytest.raises(SalonSettingsError, match="invalid salon settings"):
        resolve_public_booking_hold_seconds(settings, app_hold_seconds=900)
