from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.schedule import (
    BlockedPeriodCreateRequest,
    BlockedPeriodUpdateRequest,
    WorkingHoursCreateFields,
    WorkingHoursUpdateRequest,
)
from app.services.schedule.impact import (
    DEFAULT_HORIZON_DAYS,
    DEFAULT_IMPACT_LIMIT,
    MAX_HORIZON_DAYS,
    MAX_IMPACT_LIMIT,
)


class WorkingHoursCreateImpactChange(WorkingHoursCreateFields):
    kind: Literal["working_hours.create"]


class WorkingHoursUpdateImpactChange(WorkingHoursUpdateRequest):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["working_hours.update"]
    working_hours_id: UUID


class WorkingHoursDeleteImpactChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["working_hours.delete"]
    working_hours_id: UUID


class BlockedPeriodCreateImpactChange(BlockedPeriodCreateRequest):
    kind: Literal["blocked_period.create"]


class BlockedPeriodUpdateImpactChange(BlockedPeriodUpdateRequest):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["blocked_period.update"]
    blocked_period_id: UUID


class BlockedPeriodDeleteImpactChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["blocked_period.delete"]
    blocked_period_id: UUID


class StaffServiceDetachImpactChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["staff_service.detach"]
    staff_id: UUID
    service_id: UUID


ScheduleImpactChangeRequest = Annotated[
    WorkingHoursCreateImpactChange
    | WorkingHoursUpdateImpactChange
    | WorkingHoursDeleteImpactChange
    | BlockedPeriodCreateImpactChange
    | BlockedPeriodUpdateImpactChange
    | BlockedPeriodDeleteImpactChange
    | StaffServiceDetachImpactChange,
    Field(discriminator="kind"),
]


class ScheduleImpactPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change: ScheduleImpactChangeRequest
    horizon_days: int = Field(default=DEFAULT_HORIZON_DAYS, ge=1, le=MAX_HORIZON_DAYS)
    impact_offset: int = Field(default=0, ge=0)
    impact_limit: int = Field(default=DEFAULT_IMPACT_LIMIT, ge=1, le=MAX_IMPACT_LIMIT)


class ImpactHorizonSummary(BaseModel):
    starts_at_from: datetime
    starts_at_to: datetime
    days: int


class ScheduleImpactChangeSummary(BaseModel):
    kind: str
    affected_staff_ids: list[UUID]
    horizon: ImpactHorizonSummary


class ScheduleImpactBookingRow(BaseModel):
    booking_id: UUID
    status: str
    is_in_progress: bool
    starts_at: datetime
    ends_at: datetime
    staff_id: UUID
    service_id: UUID
    customer_name: str
    service_name: str
    reasons: list[str]


class ScheduleImpactCounts(BaseModel):
    total_impacted: int
    by_reason: dict[str, int]


class ScheduleImpactPagination(BaseModel):
    offset: int
    limit: int
    returned: int
    total_impacted: int
    has_more: bool


class ScheduleImpactCommitPolicy(BaseModel):
    allow_commit_with_impacts: bool = True
    requires_acknowledgement: bool = True


class ScheduleImpactPreviewResponse(BaseModel):
    as_of: datetime
    change_summary: ScheduleImpactChangeSummary
    impacts: list[ScheduleImpactBookingRow]
    counts: ScheduleImpactCounts
    pagination: ScheduleImpactPagination
    commit_policy: ScheduleImpactCommitPolicy
    impact_fingerprint: str
