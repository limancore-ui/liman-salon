from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SuitableServiceOut(BaseModel):
    service_id: uuid.UUID
    name: str
    duration_minutes: int
    price_cents: int
    bookable_start: datetime = Field(
        ...,
        description="Earliest actionable NET service start in this gap (UTC)",
    )


class SmartGapOut(BaseModel):
    start: datetime = Field(..., description="Gap start (timezone-aware UTC)")
    end: datetime = Field(..., description="Gap end (timezone-aware UTC)")
    suitable_services: list[SuitableServiceOut]


class SmartGapListResponse(BaseModel):
    salon_id: uuid.UUID
    staff_id: uuid.UUID
    gaps: list[SmartGapOut]
