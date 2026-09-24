from __future__ import annotations

import uuid
from datetime import date

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AsOfDep, AvailabilityServiceDep
from app.api.schemas.availability import (
    AvailabilityGapOut,
    AvailabilityResponse,
    ServiceAvailabilityResponse,
    ServiceAvailabilitySlotOut,
    StaffServiceAvailabilityOut,
)

router = APIRouter(tags=["availability"])


@router.get(
    "/salons/{salon_id}/availability",
    response_model=AvailabilityResponse,
)
def get_availability(
    salon_id: uuid.UUID,
    staff_id: uuid.UUID,
    start_date: date,
    end_date: date,
    service_duration_minutes: Annotated[int, Query(gt=0)],
    as_of: AsOfDep,
    availability: AvailabilityServiceDep,
) -> AvailabilityResponse:
    gaps = availability.get_free_gaps(
        salon_id=salon_id,
        staff_id=staff_id,
        start_date=start_date,
        end_date=end_date,
        service_duration_minutes=service_duration_minutes,
        as_of=as_of,
    )
    return AvailabilityResponse(
        gaps=[AvailabilityGapOut(start=g.start, end=g.end) for g in gaps]
    )


@router.get(
    "/salons/{salon_id}/availability/service",
    response_model=ServiceAvailabilityResponse,
)
def get_service_availability(
    salon_id: uuid.UUID,
    service_id: uuid.UUID,
    start_date: date,
    end_date: date,
    as_of: AsOfDep,
    availability: AvailabilityServiceDep,
    staff_id: uuid.UUID | None = None,
) -> ServiceAvailabilityResponse:
    result = availability.get_service_availability(
        salon_id=salon_id,
        service_id=service_id,
        start_date=start_date,
        end_date=end_date,
        staff_id=staff_id,
        as_of=as_of,
    )
    return ServiceAvailabilityResponse(
        service_id=result.service_id,
        staff=[
            StaffServiceAvailabilityOut(
                staff_id=row.staff_id,
                slots=[
                    ServiceAvailabilitySlotOut(
                        service_start=slot.service_start,
                        service_end=slot.service_end,
                    )
                    for slot in row.slots
                ],
            )
            for row in result.staff
        ],
    )
