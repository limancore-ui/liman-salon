from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicBookingCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    service_id: UUID
    staff_id: UUID
    service_start: datetime = Field(
        ...,
        description="NET service start; must be timezone-aware",
    )
    customer_notes: str | None = None


class PublicBookingCreateResponse(BaseModel):
    booking_id: UUID
    status: str
    service_id: UUID
    staff_id: UUID
    service_start: datetime
    service_end: datetime
    hold_expires_at: datetime
