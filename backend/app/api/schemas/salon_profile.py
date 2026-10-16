from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.salon_profile.service import NAME_MAX_LENGTH, normalize_salon_name
from app.services.salon_profile.errors import SalonProfileError


class SalonProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salon_id: UUID
    name: str
    slug: str


class SalonProfilePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH + 32)

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("name must be a string")
        try:
            return normalize_salon_name(value)
        except SalonProfileError as exc:
            raise ValueError(str(exc)) from exc
