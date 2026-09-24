from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AvailabilityGapOut(BaseModel):
    start: datetime = Field(..., description="Gap start (timezone-aware UTC)")
    end: datetime = Field(..., description="Gap end (timezone-aware UTC)")


class AvailabilityResponse(BaseModel):
    gaps: list[AvailabilityGapOut]


class ServiceAvailabilitySlotOut(BaseModel):
    service_start: datetime = Field(..., description="Earliest net service start (UTC)")
    service_end: datetime = Field(
        ...,
        description="Latest net service end if started at latest valid start (UTC)",
    )


class StaffServiceAvailabilityOut(BaseModel):
    staff_id: uuid.UUID
    slots: list[ServiceAvailabilitySlotOut]


class ServiceAvailabilityResponse(BaseModel):
    service_id: uuid.UUID
    staff: list[StaffServiceAvailabilityOut]
