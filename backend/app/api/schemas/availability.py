from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AvailabilityGapOut(BaseModel):
    start: datetime = Field(..., description="Gap start (timezone-aware UTC)")
    end: datetime = Field(..., description="Gap end (timezone-aware UTC)")


class AvailabilityResponse(BaseModel):
    gaps: list[AvailabilityGapOut]
