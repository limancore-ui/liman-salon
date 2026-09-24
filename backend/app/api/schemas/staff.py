from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_COLOR_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class StaffCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=100)
    bio: str | None = None
    color_hex: str | None = Field(default=None, max_length=7)
    is_bookable: bool = True
    is_active: bool = True
    sort_order: int = Field(default=0, ge=0)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be blank")
        return stripped

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _COLOR_HEX.match(value):
            raise ValueError("color_hex must match #RRGGBB")
        return value


class StaffUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=100)
    bio: str | None = None
    color_hex: str | None = Field(default=None, max_length=7)
    is_bookable: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("display_name must not be blank")
        return stripped

    @field_validator("color_hex")
    @classmethod
    def validate_color_hex(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _COLOR_HEX.match(value):
            raise ValueError("color_hex must match #RRGGBB")
        return value


class StaffResponse(BaseModel):
    id: UUID
    display_name: str
    title: str | None
    bio: str | None
    color_hex: str | None
    is_bookable: bool
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
