from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PublicSalonEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salon_id: UUID
    slug: str
    name: str
    currency_code: str
    timezone: str
    logo_media_id: UUID | None = None
