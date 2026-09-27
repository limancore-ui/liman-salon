from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class BookingCreateRequest(BaseModel):
    customer_id: UUID
    staff_id: UUID
    service_id: UUID
    requested_service_start: datetime = Field(
        ...,
        description="NET service start; must be timezone-aware",
    )
    source: str = Field(..., min_length=1, max_length=32)
    status: Literal["pending", "confirmed"]
    expires_at: datetime | None = None
    customer_notes: str | None = None
    internal_notes: str | None = None


class BookingCreateResponse(BaseModel):
    booking_id: UUID
    starts_at: datetime
    ends_at: datetime
    status: str


class BookingListItemResponse(BaseModel):
    id: UUID
    status: str
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    price_cents: int
    customer_name: str
    customer_phone: str | None
    staff_name: str
    service_name: str
    source: str
    created_at: datetime
