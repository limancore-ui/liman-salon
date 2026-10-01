from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str


class MySalonMembershipItem(BaseModel):
    salon_id: UUID
    salon_name: str
    salon_slug: str
    role: str


class MySalonsResponse(BaseModel):
    items: list[MySalonMembershipItem]


class SalonContextResponse(BaseModel):
    user_id: UUID
    salon_id: UUID
    role: str
    email: EmailStr
    salon_name: str
    salon_slug: str
    timezone: str
    currency_code: str
