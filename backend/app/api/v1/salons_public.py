from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AsOfDep, PublicBookingOrchestratorDep, SalonPublicServiceDep
from app.api.schemas.public_booking_orchestrator import (
    PublicBookingOrchestrateRequest,
    PublicBookingOrchestrateResponse,
)
from app.api.schemas.salon_public import PublicSalonEntryResponse

router = APIRouter(tags=["salons-public"])


@router.get(
    "/public/salons/{slug}",
    response_model=PublicSalonEntryResponse,
    status_code=200,
)
def get_public_salon_by_slug(
    slug: str,
    salon_public_service: SalonPublicServiceDep,
) -> PublicSalonEntryResponse:
    entry = salon_public_service.resolve_public_salon_by_slug(slug)
    return PublicSalonEntryResponse(
        salon_id=entry.salon_id,
        slug=entry.slug,
        name=entry.name,
        currency_code=entry.currency_code,
        timezone=entry.timezone,
    )


@router.post(
    "/public/salons/{slug}/bookings",
    response_model=PublicBookingOrchestrateResponse,
    status_code=201,
)
def create_public_booking_by_slug(
    slug: str,
    body: PublicBookingOrchestrateRequest,
    as_of: AsOfDep,
    orchestrator: PublicBookingOrchestratorDep,
) -> PublicBookingOrchestrateResponse:
    result = orchestrator.create_public_booking_by_slug(
        slug=slug,
        full_name=body.full_name,
        phone=body.phone,
        email=body.email,
        service_id=body.service_id,
        staff_id=body.staff_id,
        service_start=body.service_start,
        as_of=as_of,
        customer_notes=body.customer_notes,
    )
    return PublicBookingOrchestrateResponse(
        salon_id=result.salon_id,
        customer_id=result.customer_id,
        booking_id=result.booking_id,
        service_start=result.service_start,
        service_end=result.service_end,
        hold_expires_at=result.hold_expires_at,
    )
