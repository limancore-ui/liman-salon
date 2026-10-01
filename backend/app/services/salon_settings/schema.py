from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SalonBookingSettingsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_hold_seconds: int = Field(ge=60, le=3600)


class SalonSettingsV1(BaseModel):
    """v0.1 per-salon business settings stored in salons.settings JSONB."""

    model_config = ConfigDict(extra="forbid")

    v: Literal[1]
    booking: SalonBookingSettingsV1 | None = None
