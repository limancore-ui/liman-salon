from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicBookingManageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    status: str
    service_id: UUID
    service_name: str
    staff_id: UUID
    staff_display_name: str
    service_start: datetime = Field(
        description="NET service start (timezone-aware UTC recommended)",
    )
    service_end: datetime = Field(
        description="NET service end (service_start + duration)",
    )
    hold_expires_at: datetime | None = Field(
        default=None,
        description="Pending hold expiry; omitted when not applicable",
    )
    can_cancel: bool
    can_reschedule: bool
    timezone: str = Field(description="Salon IANA timezone for client display")
