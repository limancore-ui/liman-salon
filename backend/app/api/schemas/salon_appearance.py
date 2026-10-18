from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.salon_appearance.schema import SalonAppearanceColorsPatch


class SalonAppearanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salon_id: UUID
    salon_name: str
    primary_color: str | None = None
    accent_soft_color: str | None = None
    background_color: str | None = None
    logo_media_id: UUID | None = None
    background_media_id: UUID | None = None


class SalonAppearancePatchRequest(BaseModel):
    """PATCH body: omit `colors` to leave colors unchanged; null clears all colors."""

    model_config = ConfigDict(extra="forbid")

    colors: SalonAppearanceColorsPatch | None = Field(default=None)


class PublicSalonAppearanceResponse(BaseModel):
    """Safe public color overrides only (no admin-only fields)."""

    model_config = ConfigDict(extra="forbid")

    primary_color: str | None = None
    accent_soft_color: str | None = None
    background_color: str | None = None
