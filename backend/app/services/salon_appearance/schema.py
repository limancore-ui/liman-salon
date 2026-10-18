from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_hex_color(value: str) -> str:
    cleaned = value.strip()
    if not HEX_COLOR_RE.fullmatch(cleaned):
        raise ValueError("color must be a #RRGGBB hex value")
    return cleaned.lower()


class SalonAppearanceV1(BaseModel):
    """Stored appearance document (colors only; cover is Media)."""

    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = 1
    primary_color: str | None = None
    accent_soft_color: str | None = None
    background_color: str | None = None

    @field_validator(
        "primary_color",
        "accent_soft_color",
        "background_color",
        mode="before",
    )
    @classmethod
    def _validate_hex(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("color must be a string")
        if not value.strip():
            return None
        return normalize_hex_color(value)


class SalonAppearanceColorsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_color: str | None = Field(default=None)
    accent_soft_color: str | None = Field(default=None)
    background_color: str | None = Field(default=None)

    @field_validator(
        "primary_color",
        "accent_soft_color",
        "background_color",
        mode="before",
    )
    @classmethod
    def _validate_hex(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("color must be a string")
        if not value.strip():
            return None
        return normalize_hex_color(value)
