from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublicCustomerLookupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=1, max_length=32)

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("phone must not be blank")
        return stripped


class PublicCustomerLookupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool
    full_name: str | None
