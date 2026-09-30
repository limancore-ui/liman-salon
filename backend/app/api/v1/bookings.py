from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AsOfDep, BookingServiceDep, PublicBookingServiceDep
from app.api.schemas.bookings import (
    BookingCreateRequest,
    BookingCreateResponse,
    BookingListItemResponse,
)
from app.api.schemas.public_booking import (
    PublicBookingCreateRequest,
    PublicBookingCreateResponse,
)
from app.auth.deps import require_roles
from app.auth.principals import SalonContext
from app.services.booking.types import BookingListRow

router = APIRouter(tags=["bookings"])

ReadSalonContext = Annotated[
    SalonContext,
    Depends(require_roles("owner", "admin", "staff", "receptionist")),
]
WriteSalonContext = Annotated[SalonContext, Depends(require_roles("owner", "admin"))]


def _assert_path_salon(context: SalonContext, salon_id: uuid.UUID) -> None:
    if context.salon_id != salon_id:
        raise RuntimeError("salon_id path mismatch with SalonContext")


def _to_list_item(row: BookingListRow) -> BookingListItemResponse:
    return BookingListItemResponse(
        id=row.id,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        duration_minutes=row.duration_minutes,
        price_cents=row.price_cents,
        customer_name=row.customer_name,
        customer_phone=row.customer_phone,
        staff_name=row.staff_name,
        service_name=row.service_name,
        source=row.source,
        created_at=row.created_at,
    )


@router.get(
    "/salons/{salon_id}/bookings",
    response_model=list[BookingListItemResponse],
)
def list_bookings(
    salon_id: uuid.UUID,
    context: ReadSalonContext,
    booking_service: BookingServiceDep,
    starts_at_from: datetime | None = Query(default=None),
    starts_at_to: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    staff_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[BookingListItemResponse]:
    _assert_path_salon(context, salon_id)
    rows = booking_service.list_bookings(
        salon_id=context.salon_id,
        starts_at_from=starts_at_from,
        starts_at_to=starts_at_to,
        status=status,
        staff_id=staff_id,
        limit=limit,
        offset=offset,
    )
    return [_to_list_item(row) for row in rows]


@router.post(
    "/salons/{salon_id}/bookings",
    response_model=BookingCreateResponse,
    status_code=201,
)
def create_booking(
    salon_id: uuid.UUID,
    body: BookingCreateRequest,
    context: WriteSalonContext,
    as_of: AsOfDep,
    booking_service: BookingServiceDep,
) -> BookingCreateResponse:
    _assert_path_salon(context, salon_id)
    result = booking_service.create_booking(
        salon_id=context.salon_id,
        customer_id=body.customer_id,
        staff_id=body.staff_id,
        service_id=body.service_id,
        requested_service_start=body.requested_service_start,
        source="admin",
        status=body.status,
        as_of=as_of,
        expires_at=body.expires_at,
        customer_notes=body.customer_notes,
        internal_notes=body.internal_notes,
        created_by_user_id=context.user_id,
    )
    return BookingCreateResponse(
        booking_id=result.booking_id,
        starts_at=result.starts_at,
        ends_at=result.ends_at,
        status=result.status,
    )


@router.post(
    "/salons/{salon_id}/bookings/public",
    response_model=PublicBookingCreateResponse,
    status_code=201,
)
def create_public_booking(
    salon_id: uuid.UUID,
    body: PublicBookingCreateRequest,
    as_of: AsOfDep,
    public_booking_service: PublicBookingServiceDep,
) -> PublicBookingCreateResponse:
    result = public_booking_service.create_public_booking(
        salon_id=salon_id,
        customer_id=body.customer_id,
        staff_id=body.staff_id,
        service_id=body.service_id,
        service_start=body.service_start,
        as_of=as_of,
        customer_notes=body.customer_notes,
    )
    return PublicBookingCreateResponse(
        booking_id=result.booking_id,
        status=result.status,
        service_id=result.service_id,
        staff_id=result.staff_id,
        service_start=result.service_start,
        service_end=result.service_end,
        hold_expires_at=result.hold_expires_at,
        manage_token=result.manage_token,
    )
