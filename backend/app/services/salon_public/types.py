from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicSalonAppearanceColors:
    primary_color: str | None = None
    accent_soft_color: str | None = None
    background_color: str | None = None


@dataclass(frozen=True, slots=True)
class PublicSalonEntry:
    salon_id: uuid.UUID
    slug: str
    name: str
    currency_code: str
    timezone: str
    logo_media_id: uuid.UUID | None = None
    background_media_id: uuid.UUID | None = None
    appearance: PublicSalonAppearanceColors | None = None
