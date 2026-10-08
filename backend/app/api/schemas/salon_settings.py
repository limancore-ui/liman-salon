from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SalonBookingSettingsResponse(BaseModel):
    public_hold_seconds: int = Field(ge=60, le=3600)


class SalonBonusesSettingsResponse(BaseModel):
    enabled: bool
    earn_percentage: float = Field(ge=0)


class SalonSettingsResponse(BaseModel):
    v: Literal[1] = 1
    booking: SalonBookingSettingsResponse | None = None
    bonuses: SalonBonusesSettingsResponse | None = None


class SalonBookingSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_hold_seconds: int = Field(ge=60, le=3600)


class SalonBonusesSettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    earn_percentage: float = Field(ge=0)


class SalonSettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking: SalonBookingSettingsPatch | None = None
    bonuses: SalonBonusesSettingsPatch | None = None
