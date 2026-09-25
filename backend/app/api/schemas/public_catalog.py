from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class PublicCatalogServiceOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price_cents: int
    currency_code: str


class PublicCatalogServicesResponse(BaseModel):
    salon_id: UUID
    services: list[PublicCatalogServiceOut]


class PublicCatalogStaffOut(BaseModel):
    id: UUID
    display_name: str


class PublicCatalogStaffResponse(BaseModel):
    salon_id: UUID
    service_id: UUID
    staff: list[PublicCatalogStaffOut] = Field(default_factory=list)
