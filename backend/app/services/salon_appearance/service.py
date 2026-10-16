from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.services.media.repository import MediaRepository
from app.services.media.types import MediaEntityType, MediaPurpose
from app.services.salon_appearance.errors import (
    SalonAppearanceError,
    SalonAppearanceNotFoundError,
)
from app.services.salon_appearance.repository import SalonAppearanceRepository
from app.services.salon_appearance.schema import (
    SalonAppearanceColorsPatch,
    SalonAppearanceV1,
)


@dataclass(frozen=True, slots=True)
class SalonAppearanceView:
    salon_id: uuid.UUID
    salon_name: str
    primary_color: str | None
    accent_soft_color: str | None
    background_color: str | None
    logo_media_id: uuid.UUID | None
    background_media_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class SalonAppearancePatchData:
    """When colors_set is True, colors may be None to clear all overrides."""

    colors_set: bool
    colors: SalonAppearanceColorsPatch | None = None


def validate_stored_appearance(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = SalonAppearanceV1.model_validate(raw)
    except ValidationError as exc:
        raise SalonAppearanceError("invalid salon appearance") from exc
    dumped = parsed.model_dump(exclude_none=True)
    if list(dumped.keys()) == ["v"]:
        return {}
    return dumped


def merge_appearance_patch(
    current: dict[str, Any],
    patch: SalonAppearancePatchData,
) -> dict[str, Any]:
    if not patch.colors_set:
        return dict(current)
    if patch.colors is None:
        return {}
    merged = dict(current)
    merged["v"] = 1
    data = patch.colors.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return validate_stored_appearance(merged)


class SalonAppearanceService:
    def __init__(self, session: Session) -> None:
        self._repo = SalonAppearanceRepository(session)
        self._media_repo = MediaRepository(session)

    def get_appearance(self, *, salon_id: uuid.UUID) -> SalonAppearanceView:
        if not self._repo.salon_exists(salon_id):
            raise SalonAppearanceNotFoundError("salon not found")
        raw = self._load_raw(salon_id)
        return self._to_view(salon_id, raw)

    def patch_appearance(
        self,
        *,
        salon_id: uuid.UUID,
        patch: SalonAppearancePatchData,
    ) -> SalonAppearanceView:
        if not self._repo.salon_exists(salon_id):
            raise SalonAppearanceNotFoundError("salon not found")
        current = self._load_raw(salon_id)
        merged = merge_appearance_patch(current, patch)
        if not self._repo.update_appearance(salon_id, merged):
            raise SalonAppearanceNotFoundError("salon not found")
        return self._to_view(salon_id, merged)

    def _load_raw(self, salon_id: uuid.UUID) -> dict[str, Any]:
        raw = self._repo.get_appearance(salon_id)
        if raw is None:
            return {}
        if not isinstance(raw, dict):
            raise SalonAppearanceError("salon appearance must be a JSON object")
        return validate_stored_appearance(dict(raw))

    def _to_view(
        self, salon_id: uuid.UUID, stored: dict[str, Any]
    ) -> SalonAppearanceView:
        name = self._repo.get_salon_name(salon_id) or ""
        primary = None
        accent = None
        background = None
        if stored:
            try:
                parsed = SalonAppearanceV1.model_validate(stored)
            except ValidationError as exc:
                raise SalonAppearanceError("invalid salon appearance") from exc
            primary = parsed.primary_color
            accent = parsed.accent_soft_color
            background = parsed.background_color

        logo_media_id = self._media_repo.resolve_attached_media_id(
            salon_id=salon_id,
            entity_type=MediaEntityType.SALON,
            entity_id=salon_id,
            purpose=MediaPurpose.LOGO,
        )
        background_media_id = self._media_repo.resolve_attached_media_id(
            salon_id=salon_id,
            entity_type=MediaEntityType.SALON,
            entity_id=salon_id,
            purpose=MediaPurpose.COVER,
        )
        return SalonAppearanceView(
            salon_id=salon_id,
            salon_name=name,
            primary_color=primary,
            accent_soft_color=accent,
            background_color=background,
            logo_media_id=logo_media_id,
            background_media_id=background_media_id,
        )
