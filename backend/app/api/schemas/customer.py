from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    notes: str | None = None
    marketing_opt_in: bool = False
    whatsapp_opt_in: bool = False

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("full_name must not be blank")
        return stripped


class CustomerUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=320)
    notes: str | None = None
    marketing_opt_in: bool | None = None
    whatsapp_opt_in: bool | None = None

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("full_name must not be blank")
        return stripped


class CustomerResponse(BaseModel):
    id: UUID
    salon_id: UUID
    user_id: UUID | None
    full_name: str
    email: str | None
    phone: str | None
    notes: str | None
    bonus_balance_cents: int
    marketing_opt_in: bool
    whatsapp_opt_in: bool
    whatsapp_opt_in_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PublicCustomerResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    email: str | None = Field(default=None, max_length=320)

    @field_validator("full_name")
    @classmethod
    def strip_full_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("full_name must not be blank")
        return stripped

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("phone must not be blank")
        return stripped


class PublicCustomerResolveResponse(BaseModel):
    customer_id: UUID
    created: bool
