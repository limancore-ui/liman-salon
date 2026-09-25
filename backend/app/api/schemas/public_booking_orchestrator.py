from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicBookingOrchestrateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(..., min_length=1, max_length=32)
    full_name: str = Field(..., min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    service_id: UUID
    staff_id: UUID
    service_start: datetime = Field(
        ...,
        description="NET service start; must be timezone-aware",
    )
    customer_notes: str | None = None


class PublicBookingOrchestrateResponse(BaseModel):
    salon_id: UUID
    customer_id: UUID
    booking_id: UUID
    service_start: datetime
    service_end: datetime
    hold_expires_at: datetime
