from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import ScheduleServiceDep
from app.api.schemas.schedule import (
    BlockedPeriodCreateRequest,
    BlockedPeriodResponse,
    BlockedPeriodUpdateRequest,
    WorkingHoursCreateRequest,
    WorkingHoursResponse,
    WorkingHoursUpdateRequest,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.schedule.service import (
    BlockedPeriodCreateData,
    BlockedPeriodUpdateData,
    WorkingHoursCreateData,
    WorkingHoursUpdateData,
)

router = APIRouter(prefix="/salons/{salon_id}/schedule", tags=["schedule"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


def _working_hours_update_data(body: WorkingHoursUpdateRequest) -> WorkingHoursUpdateData:
    fields = body.model_fields_set
    return WorkingHoursUpdateData(
        staff_id=body.staff_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        set_staff_id="staff_id" in fields,
        set_effective_from="effective_from" in fields,
        set_effective_to="effective_to" in fields,
    )


def _blocked_period_update_data(body: BlockedPeriodUpdateRequest) -> BlockedPeriodUpdateData:
    fields = body.model_fields_set
    return BlockedPeriodUpdateData(
        staff_id=body.staff_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        reason=body.reason,
        block_type=body.block_type,
        set_staff_id="staff_id" in fields,
        set_reason="reason" in fields,
    )


@router.get("/working-hours", response_model=list[WorkingHoursResponse])
def list_working_hours(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    schedule_service: ScheduleServiceDep,
    staff_id: uuid.UUID | None = Query(default=None),
) -> list[WorkingHoursResponse]:
    _assert_path_salon(context, salon_id)
    rows = schedule_service.list_working_hours(
        salon_id=context.salon_id,
        staff_id=staff_id,
    )
    return [WorkingHoursResponse.model_validate(row) for row in rows]


@router.post("/working-hours", response_model=WorkingHoursResponse, status_code=201)
def create_working_hours(
    salon_id: uuid.UUID,
    body: WorkingHoursCreateRequest,
    context: WriteSalonContext,
    schedule_service: ScheduleServiceDep,
) -> WorkingHoursResponse:
    _assert_path_salon(context, salon_id)
    row = schedule_service.create_working_hour(
        salon_id=context.salon_id,
        data=WorkingHoursCreateData(
            staff_id=body.staff_id,
            day_of_week=body.day_of_week,
            start_time=body.start_time,
            end_time=body.end_time,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
        ),
    )
    return WorkingHoursResponse.model_validate(row)


@router.get("/working-hours/{working_hours_id}", response_model=WorkingHoursResponse)
def get_working_hours(
    salon_id: uuid.UUID,
    working_hours_id: uuid.UUID,
    context: ReadSalonContext,
    schedule_service: ScheduleServiceDep,
) -> WorkingHoursResponse:
    _assert_path_salon(context, salon_id)
    row = schedule_service.get_working_hour(
        salon_id=context.salon_id,
        working_hours_id=working_hours_id,
    )
    return WorkingHoursResponse.model_validate(row)


@router.patch("/working-hours/{working_hours_id}", response_model=WorkingHoursResponse)
def update_working_hours(
    salon_id: uuid.UUID,
    working_hours_id: uuid.UUID,
    body: WorkingHoursUpdateRequest,
    context: WriteSalonContext,
    schedule_service: ScheduleServiceDep,
) -> WorkingHoursResponse:
    _assert_path_salon(context, salon_id)
    row = schedule_service.update_working_hour(
        salon_id=context.salon_id,
        working_hours_id=working_hours_id,
        data=_working_hours_update_data(body),
    )
    return WorkingHoursResponse.model_validate(row)


@router.delete("/working-hours/{working_hours_id}", status_code=204)
def delete_working_hours(
    salon_id: uuid.UUID,
    working_hours_id: uuid.UUID,
    context: WriteSalonContext,
    schedule_service: ScheduleServiceDep,
) -> Response:
    _assert_path_salon(context, salon_id)
    schedule_service.delete_working_hour(
        salon_id=context.salon_id,
        working_hours_id=working_hours_id,
    )
    return Response(status_code=204)


@router.get("/blocked-periods", response_model=list[BlockedPeriodResponse])
def list_blocked_periods(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    schedule_service: ScheduleServiceDep,
    staff_id: uuid.UUID | None = Query(default=None),
    starts_from: datetime | None = Query(default=None),
    ends_to: datetime | None = Query(default=None),
    block_type: Literal["manual", "holiday", "time_off"] | None = Query(default=None),
) -> list[BlockedPeriodResponse]:
    _assert_path_salon(context, salon_id)
    rows = schedule_service.list_blocked_periods(
        salon_id=context.salon_id,
        staff_id=staff_id,
        starts_from=starts_from,
        ends_to=ends_to,
        block_type=block_type,
    )
    return [BlockedPeriodResponse.model_validate(row) for row in rows]


@router.post("/blocked-periods", response_model=BlockedPeriodResponse, status_code=201)
def create_blocked_period(
    salon_id: uuid.UUID,
    body: BlockedPeriodCreateRequest,
    context: WriteSalonContext,
    schedule_service: ScheduleServiceDep,
) -> BlockedPeriodResponse:
    _assert_path_salon(context, salon_id)
    row = schedule_service.create_blocked_period(
        salon_id=context.salon_id,
        created_by_user_id=context.user_id,
        data=BlockedPeriodCreateData(
            staff_id=body.staff_id,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            reason=body.reason,
            block_type=body.block_type,
        ),
    )
    return BlockedPeriodResponse.model_validate(row)


@router.get("/blocked-periods/{blocked_period_id}", response_model=BlockedPeriodResponse)
def get_blocked_period(
    salon_id: uuid.UUID,
    blocked_period_id: uuid.UUID,
    context: ReadSalonContext,
    schedule_service: ScheduleServiceDep,
) -> BlockedPeriodResponse:
    _assert_path_salon(context, salon_id)
    row = schedule_service.get_blocked_period(
        salon_id=context.salon_id,
        blocked_period_id=blocked_period_id,
    )
    return BlockedPeriodResponse.model_validate(row)


@router.patch("/blocked-periods/{blocked_period_id}", response_model=BlockedPeriodResponse)
def update_blocked_period(
    salon_id: uuid.UUID,
    blocked_period_id: uuid.UUID,
    body: BlockedPeriodUpdateRequest,
    context: WriteSalonContext,
    schedule_service: ScheduleServiceDep,
) -> BlockedPeriodResponse:
    _assert_path_salon(context, salon_id)
    row = schedule_service.update_blocked_period(
        salon_id=context.salon_id,
        blocked_period_id=blocked_period_id,
        data=_blocked_period_update_data(body),
    )
    return BlockedPeriodResponse.model_validate(row)


@router.delete("/blocked-periods/{blocked_period_id}", status_code=204)
def delete_blocked_period(
    salon_id: uuid.UUID,
    blocked_period_id: uuid.UUID,
    context: WriteSalonContext,
    schedule_service: ScheduleServiceDep,
) -> Response:
    _assert_path_salon(context, salon_id)
    schedule_service.delete_blocked_period(
        salon_id=context.salon_id,
        blocked_period_id=blocked_period_id,
    )
    return Response(status_code=204)
