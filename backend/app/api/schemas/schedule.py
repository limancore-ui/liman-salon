from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkingHoursCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: UUID | None = None
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    effective_from: date | None = None
    effective_to: date | None = None

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, end_time: time, info) -> time:
        start = info.data.get("start_time")
        if start is not None and end_time <= start:
            raise ValueError("start_time must be before end_time")
        return end_time

    @field_validator("effective_to")
    @classmethod
    def effective_range(cls, effective_to: date | None, info) -> date | None:
        effective_from = info.data.get("effective_from")
        if (
            effective_from is not None
            and effective_to is not None
            and effective_to < effective_from
        ):
            raise ValueError("effective_to must be on or after effective_from")
        return effective_to


class WorkingHoursUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: UUID | None = None
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class WorkingHoursResponse(BaseModel):
    id: UUID
    staff_id: UUID | None
    day_of_week: int
    start_time: time
    end_time: time
    effective_from: date | None
    effective_to: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


BlockType = Literal["manual", "holiday", "time_off"]


class BlockedPeriodCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: UUID | None = None
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=255)
    block_type: BlockType = "manual"

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value

    @field_validator("ends_at")
    @classmethod
    def ends_after_starts(cls, ends_at: datetime, info) -> datetime:
        starts_at = info.data.get("starts_at")
        if starts_at is not None and ends_at <= starts_at:
            raise ValueError("starts_at must be before ends_at")
        return ends_at


class BlockedPeriodUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=255)
    block_type: BlockType | None = None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_tz_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value


class BlockedPeriodResponse(BaseModel):
    id: UUID
    staff_id: UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None
    block_type: str
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
