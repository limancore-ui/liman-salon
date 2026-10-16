from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.schemas.salon_appearance import PublicSalonAppearanceResponse


class PublicSalonEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salon_id: UUID
    slug: str
    name: str
    currency_code: str
    timezone: str
    logo_media_id: UUID | None = None
    background_media_id: UUID | None = None
    appearance: PublicSalonAppearanceResponse | None = None
