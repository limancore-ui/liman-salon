from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.services.salon_settings.errors import SalonSettingsError
from app.services.salon_settings.schema import SalonSettingsV1


@dataclass(frozen=True, slots=True)
class BonusEarnPolicy:
    enabled: bool = False
    earn_percentage: float = 0


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


def resolve_bonus_earn_policy(salon_settings: Any) -> BonusEarnPolicy:
    """
    Bonus earn policy from salons.settings JSONB.

    Missing or empty JSONB → disabled with 0% earn (silent no-op on earn path).
    """
    if salon_settings is None:
        return BonusEarnPolicy()
    if not isinstance(salon_settings, dict):
        raise SalonSettingsError("salon settings must be a JSON object")
    if not salon_settings:
        return BonusEarnPolicy()

    try:
        parsed = SalonSettingsV1.model_validate(salon_settings)
    except ValidationError as exc:
        raise SalonSettingsError("invalid salon settings") from exc

    if parsed.bonuses is None:
        return BonusEarnPolicy()
    return BonusEarnPolicy(
        enabled=parsed.bonuses.enabled,
        earn_percentage=parsed.bonuses.earn_percentage,
    )


def compute_earn_amount_cents(*, price_cents: int, policy: BonusEarnPolicy) -> int:
    if price_cents < 0:
        raise ValueError("price_cents must be >= 0")
    if not policy.enabled or policy.earn_percentage <= 0:
        return 0
    return int(price_cents * policy.earn_percentage // 100)
