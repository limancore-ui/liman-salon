from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.services.salon_settings.errors import (
    SalonSettingsError,
    SalonSettingsNotFoundError,
)
from app.services.salon_settings.repository import SalonSettingsRepository
from app.services.salon_settings.schema import SalonSettingsV1


@dataclass(frozen=True, slots=True)
class SalonBookingPatchData:
    public_hold_seconds: int


@dataclass(frozen=True, slots=True)
class SalonBonusesPatchData:
    enabled: bool
    earn_percentage: float


@dataclass(frozen=True, slots=True)
class SalonSettingsPatchData:
    booking_set: bool
    booking: SalonBookingPatchData | None = None
    bonuses_set: bool = False
    bonuses: SalonBonusesPatchData | None = None


@dataclass(frozen=True, slots=True)
class SalonSettingsView:
    stored: dict[str, Any]
    v: int
    public_hold_seconds: int | None
    bonuses_enabled: bool | None = None
    bonuses_earn_percentage: float | None = None


class SalonSettingsService:
    def __init__(self, session: Session, *, app_hold_seconds: int) -> None:
        self._repo = SalonSettingsRepository(session)
        self._app_hold_seconds = app_hold_seconds

    def get_settings(self, *, salon_id: uuid.UUID) -> SalonSettingsView:
        raw = self._load_raw(salon_id)
        return self._to_view(raw)

    def patch_settings(
        self,
        *,
        salon_id: uuid.UUID,
        patch: SalonSettingsPatchData,
    ) -> SalonSettingsView:
        current = self._load_raw(salon_id)
        merged = merge_settings_patch(current, patch)
        validated = validate_stored_settings(merged)
        if not self._repo.update_settings(salon_id, validated):
            raise SalonSettingsNotFoundError("salon not found")
        return self._to_view(validated)

    def _load_raw(self, salon_id: uuid.UUID) -> dict[str, Any]:
        if not self._repo.salon_exists(salon_id):
            raise SalonSettingsNotFoundError("salon not found")
        raw = self._repo.get_settings(salon_id)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise SalonSettingsError("salon settings must be a JSON object")
        return dict(raw)

    def _to_view(self, stored: dict[str, Any]) -> SalonSettingsView:
        public_hold: int | None = None
        bonuses_enabled: bool | None = None
        bonuses_earn_percentage: float | None = None
        if stored:
            try:
                parsed = SalonSettingsV1.model_validate(stored)
            except ValidationError as exc:
                raise SalonSettingsError("invalid salon settings") from exc
            if parsed.booking is not None:
                public_hold = parsed.booking.public_hold_seconds
            if parsed.bonuses is not None:
                bonuses_enabled = parsed.bonuses.enabled
                bonuses_earn_percentage = parsed.bonuses.earn_percentage
            v = parsed.v
        else:
            v = 1
        return SalonSettingsView(
            stored=stored,
            v=v,
            public_hold_seconds=public_hold,
            bonuses_enabled=bonuses_enabled,
            bonuses_earn_percentage=bonuses_earn_percentage,
        )


def merge_settings_patch(
    current: dict[str, Any],
    patch: SalonSettingsPatchData,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(current)
    if patch.booking_set:
        if patch.booking is None:
            merged.pop("booking", None)
        else:
            booking_patch = patch.booking
            merged["booking"] = {
                "public_hold_seconds": booking_patch.public_hold_seconds,
            }

    if patch.bonuses_set:
        if patch.bonuses is None:
            merged.pop("bonuses", None)
        else:
            bonuses_patch = patch.bonuses
            merged["bonuses"] = {
                "enabled": bonuses_patch.enabled,
                "earn_percentage": bonuses_patch.earn_percentage,
            }

    return normalize_stored_settings(merged)


def normalize_stored_settings(merged: dict[str, Any]) -> dict[str, Any]:
    if not merged:
        return {}
    if "booking" not in merged and "bonuses" not in merged:
        return {}
    merged["v"] = 1
    return merged


def validate_stored_settings(stored: dict[str, Any]) -> dict[str, Any]:
    if not stored:
        return {}
    try:
        parsed = SalonSettingsV1.model_validate(stored)
    except ValidationError as exc:
        raise SalonSettingsError("invalid salon settings") from exc
    if parsed.booking is None and parsed.bonuses is None:
        return {}
    return parsed.model_dump(mode="json", exclude_none=True)
