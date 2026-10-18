from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.showcase.types import ShowcaseCategory

_MAX_INTEGER = 2_147_483_647


class ShowcaseItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ShowcaseCategory
    title: str = Field(min_length=1, max_length=200)
    media_asset_id: UUID
    description: str | None = None
    price_cents: int | None = Field(default=None, strict=True, ge=0, le=_MAX_INTEGER)
    sort_order: int = Field(default=0, strict=True, ge=0, le=_MAX_INTEGER)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title


class ShowcaseItemPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: ShowcaseCategory | None = None
    price_cents: int | None = Field(default=None, strict=True, ge=0, le=_MAX_INTEGER)
    media_asset_id: UUID | None = None
    sort_order: int | None = Field(default=None, strict=True, ge=0, le=_MAX_INTEGER)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title:
            raise ValueError("title must not be blank")
        return title

    @model_validator(mode="after")
    def validate_patch(self) -> ShowcaseItemPatchRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        for field in ("title", "category", "media_asset_id", "sort_order"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ShowcaseItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    salon_id: UUID
    category: ShowcaseCategory
    title: str
    description: str | None
    price_cents: int | None
    media_asset_id: UUID
    sort_order: int
    is_published: bool
    created_at: datetime
    updated_at: datetime


class PublicShowcaseItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    category: ShowcaseCategory
    title: str
    description: str | None
    price_cents: int | None
    image_url: str


class PublicShowcaseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salon_id: UUID
    items: list[PublicShowcaseItemResponse]
