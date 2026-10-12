from __future__ import annotations

from app.api.schemas.schedule_impact import (
    BlockedPeriodCreateImpactChange,
    BlockedPeriodDeleteImpactChange,
    BlockedPeriodUpdateImpactChange,
    ScheduleImpactChangeRequest,
    StaffServiceDetachImpactChange,
    WorkingHoursCreateImpactChange,
    WorkingHoursDeleteImpactChange,
    WorkingHoursUpdateImpactChange,
)
from app.services.schedule.overlay import (
    BlockedPeriodCreateChange,
    BlockedPeriodDeleteChange,
    BlockedPeriodUpdateChange,
    ScheduleImpactChange,
    StaffServiceDetachChange,
    WorkingHoursCreateChange,
    WorkingHoursDeleteChange,
    WorkingHoursUpdateChange,
)


def map_impact_change_request(change: ScheduleImpactChangeRequest) -> ScheduleImpactChange:
    if isinstance(change, WorkingHoursCreateImpactChange):
        return WorkingHoursCreateChange(
            staff_id=change.staff_id,
            day_of_week=change.day_of_week,
            start_time=change.start_time,
            end_time=change.end_time,
            effective_from=change.effective_from,
            effective_to=change.effective_to,
        )
    if isinstance(change, WorkingHoursUpdateImpactChange):
        fields = change.model_fields_set
        return WorkingHoursUpdateChange(
            working_hours_id=change.working_hours_id,
            staff_id=change.staff_id,
            day_of_week=change.day_of_week,
            start_time=change.start_time,
            end_time=change.end_time,
            effective_from=change.effective_from,
            effective_to=change.effective_to,
            set_staff_id="staff_id" in fields,
            set_effective_from="effective_from" in fields,
            set_effective_to="effective_to" in fields,
        )
    if isinstance(change, WorkingHoursDeleteImpactChange):
        return WorkingHoursDeleteChange(working_hours_id=change.working_hours_id)
    if isinstance(change, BlockedPeriodCreateImpactChange):
        return BlockedPeriodCreateChange(
            staff_id=change.staff_id,
            starts_at=change.starts_at,
            ends_at=change.ends_at,
            block_type=change.block_type,
        )
    if isinstance(change, BlockedPeriodUpdateImpactChange):
        fields = change.model_fields_set
        return BlockedPeriodUpdateChange(
            blocked_period_id=change.blocked_period_id,
            staff_id=change.staff_id,
            starts_at=change.starts_at,
            ends_at=change.ends_at,
            set_staff_id="staff_id" in fields,
        )
    if isinstance(change, BlockedPeriodDeleteImpactChange):
        return BlockedPeriodDeleteChange(blocked_period_id=change.blocked_period_id)
    if isinstance(change, StaffServiceDetachImpactChange):
        return StaffServiceDetachChange(
            staff_id=change.staff_id,
            service_id=change.service_id,
        )
    raise ValueError("unsupported impact change")
