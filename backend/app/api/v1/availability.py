from __future__ import annotations

import uuid
from datetime import date

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AsOfDep, AvailabilityServiceDep
from app.api.schemas.availability import AvailabilityGapOut, AvailabilityResponse

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
