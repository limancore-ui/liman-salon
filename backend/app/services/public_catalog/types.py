from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PublicCatalogServiceItem:
    id: uuid.UUID
    name: str
    description: str | None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price_cents: int
    currency_code: str
    cover_media_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class PublicCatalogServicesResult:
    salon_id: uuid.UUID
    services: tuple[PublicCatalogServiceItem, ...]


@dataclass(frozen=True, slots=True)
class PublicCatalogStaffMember:
    id: uuid.UUID
    display_name: str
    avatar_media_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class PublicCatalogStaffResult:
    salon_id: uuid.UUID
    service_id: uuid.UUID
    staff: tuple[PublicCatalogStaffMember, ...]
