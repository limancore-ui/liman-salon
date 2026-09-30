from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicBookingRescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, description="Manage token from booking creation")
    staff_id: UUID
    service_start: datetime = Field(
        description="NET service start (timezone-aware UTC recommended)",
    )


class PublicBookingRescheduleResponse(BaseModel):
    booking_id: UUID
    status: str
    staff_id: UUID
    service_start: datetime
    service_end: datetime
