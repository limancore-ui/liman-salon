from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ServiceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    duration_minutes: int = Field(default=30, gt=0)
    buffer_before_minutes: int = Field(default=0, ge=0)
    buffer_after_minutes: int = Field(default=0, ge=0)
    price_cents: int = Field(default=0, ge=0)
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class ServiceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    buffer_before_minutes: int | None = Field(default=None, ge=0)
    buffer_after_minutes: int | None = Field(default=None, ge=0)
    price_cents: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped


class ServiceResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
    price_cents: int
    is_active: bool
    sort_order: int
    currency_code: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
