from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import AsOfDep, SmartGapServiceDep
from app.api.schemas.smart_gap import (
    SmartGapListResponse,
    SmartGapOut,
    SuitableServiceOut,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.smart_gap.types import SmartGapResult

router = APIRouter(tags=["smart-gaps"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


def _to_response(result: SmartGapResult) -> SmartGapListResponse:
    return SmartGapListResponse(
        salon_id=result.salon_id,
        staff_id=result.staff_id,
        gaps=[
            SmartGapOut(
                start=entry.gap.start,
                end=entry.gap.end,
                suitable_services=[
                    SuitableServiceOut(
                        service_id=s.service_id,
                        name=s.name,
                        duration_minutes=s.duration_minutes,
                        price_cents=s.price_cents,
                    )
                    for s in entry.suitable_services
                ],
            )
            for entry in result.entries
        ],
    )


@router.get(
    "/salons/{salon_id}/smart-gaps",
    response_model=SmartGapListResponse,
)
def list_smart_gaps(
    salon_id: uuid.UUID,
    staff_id: uuid.UUID,
    start_date: date,
    end_date: date,
    context: ReadSalonContext,
    as_of: AsOfDep,
    smart_gap_service: SmartGapServiceDep,
) -> SmartGapListResponse:
    _assert_path_salon(context, salon_id)
    result = smart_gap_service.get_gaps_with_suitable_services(
        salon_id=context.salon_id,
        staff_id=staff_id,
        start_date=start_date,
        end_date=end_date,
        as_of=as_of,
    )
    return _to_response(result)
