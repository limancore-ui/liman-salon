from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicBookingCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, description="Manage token from booking creation")
    reason: str | None = Field(
        default=None,
        max_length=255,
        description="Optional cancellation reason",
    )


class PublicBookingCancelResponse(BaseModel):
    booking_id: UUID
    status: str
    cancelled_at: datetime
