from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import AsOfDep, BookingServiceDep
from app.api.schemas.bookings import BookingCreateRequest, BookingCreateResponse

router = APIRouter(tags=["bookings"])


@router.post(
    "/salons/{salon_id}/bookings",
    response_model=BookingCreateResponse,
    status_code=201,
)
def create_booking(
    salon_id: uuid.UUID,
    body: BookingCreateRequest,
    as_of: AsOfDep,
    booking_service: BookingServiceDep,
) -> BookingCreateResponse:
    result = booking_service.create_booking(
        salon_id=salon_id,
        customer_id=body.customer_id,
        staff_id=body.staff_id,
        service_id=body.service_id,
        requested_service_start=body.requested_service_start,
        source=body.source,
        status=body.status,
        as_of=as_of,
        expires_at=body.expires_at,
        customer_notes=body.customer_notes,
        internal_notes=body.internal_notes,
    )
    return BookingCreateResponse(
        booking_id=result.booking_id,
        starts_at=result.starts_at,
        ends_at=result.ends_at,
        status=result.status,
    )
