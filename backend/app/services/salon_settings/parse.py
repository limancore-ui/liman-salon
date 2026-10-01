from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.services.salon_settings.errors import SalonSettingsError
from app.services.salon_settings.schema import SalonSettingsV1


def resolve_public_booking_hold_seconds(
    salon_settings: Any,
    *,
    app_hold_seconds: int,
) -> int:
    """
    Hold TTL resolution: salon override → application/env setting.

    Empty or missing JSONB ({}) preserves existing env/default behavior.
    """
    override = _salon_public_hold_override(salon_settings)
    if override is not None:
        return override
    return app_hold_seconds


def _salon_public_hold_override(salon_settings: Any) -> int | None:
    if salon_settings is None:
        return None
    if not isinstance(salon_settings, dict):
        raise SalonSettingsError("salon settings must be a JSON object")
    if not salon_settings:
        return None

    try:
        parsed = SalonSettingsV1.model_validate(salon_settings)
    except ValidationError as exc:
        raise SalonSettingsError("invalid salon settings") from exc

    if parsed.booking is None:
        return None
    return parsed.booking.public_hold_seconds
