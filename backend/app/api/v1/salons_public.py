from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import (
    AsOfDep,
    BookingServiceDep,
    CustomerServiceDep,
    MediaServiceDep,
    PublicBookingOrchestratorDep,
    PublicCatalogServiceDep,
    SalonPublicServiceDep,
)
from app.api.schemas.public_booking_cancel import (
    PublicBookingCancelRequest,
    PublicBookingCancelResponse,
)
from app.api.schemas.availability import (
    ServiceAvailabilityResponse,
    ServiceAvailabilitySlotOut,
    StaffServiceAvailabilityOut,
)
from app.api.schemas.public_booking_orchestrator import (
    PublicBookingOrchestrateRequest,
    PublicBookingOrchestrateResponse,
)
from app.api.schemas.public_catalog import (
    PublicCatalogServiceOut,
    PublicCatalogServicesResponse,
    PublicCatalogStaffOut,
    PublicCatalogStaffResponse,
)
from app.api.schemas.public_customer import (
    PublicCustomerLookupRequest,
    PublicCustomerLookupResponse,
)
from app.api.schemas.salon_public import PublicSalonEntryResponse
from app.services.availability.types import ServiceAvailabilityResult

router = APIRouter(tags=["salons-public"])


def _to_service_availability_response(
    result: ServiceAvailabilityResult,
) -> ServiceAvailabilityResponse:
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


@router.get(
    "/public/salons/{slug}/customer",
    response_model=PublicCustomerLookupResponse,
    status_code=200,
)
def lookup_public_customer_by_slug(
    slug: str,
    query: Annotated[PublicCustomerLookupRequest, Query()],
    salon_public_service: SalonPublicServiceDep,
    customer_service: CustomerServiceDep,
) -> PublicCustomerLookupResponse:
    entry = salon_public_service.resolve_public_salon_by_slug(slug)
    result = customer_service.lookup_public_customer(
        salon_id=entry.salon_id,
        phone=query.phone,
    )
    return PublicCustomerLookupResponse(
        found=result.found,
        full_name=result.full_name,
    )


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
        logo_media_id=entry.logo_media_id,
    )


@router.get(
    "/public/salons/{slug}/media/{media_id}/content",
    status_code=200,
)
def get_public_media_content_by_slug(
    slug: str,
    media_id: uuid.UUID,
    salon_public_service: SalonPublicServiceDep,
    media_service: MediaServiceDep,
) -> StreamingResponse:
    entry = salon_public_service.resolve_public_salon_by_slug(slug)
    asset, stream = media_service.open_public_asset_content(
        salon_id=entry.salon_id,
        media_id=media_id,
    )
    headers: dict[str, str] = {"Cache-Control": "public, max-age=86400"}
    if asset.checksum_sha256:
        headers["ETag"] = f'"{asset.checksum_sha256}"'
    return StreamingResponse(
        stream,
        media_type=asset.content_type,
        headers=headers,
    )


@router.get(
    "/public/salons/{slug}/services",
    response_model=PublicCatalogServicesResponse,
    status_code=200,
)
def list_public_services_by_slug(
    slug: str,
    catalog: PublicCatalogServiceDep,
) -> PublicCatalogServicesResponse:
    result = catalog.list_active_services_by_slug(slug)
    return PublicCatalogServicesResponse(
        salon_id=result.salon_id,
        services=[
            PublicCatalogServiceOut(
                id=item.id,
                name=item.name,
                description=item.description,
                duration_minutes=item.duration_minutes,
                buffer_before_minutes=item.buffer_before_minutes,
                buffer_after_minutes=item.buffer_after_minutes,
                price_cents=item.price_cents,
                currency_code=item.currency_code,
                cover_media_id=item.cover_media_id,
            )
            for item in result.services
        ],
    )


@router.get(
    "/public/salons/{slug}/services/{service_id}/staff",
    response_model=PublicCatalogStaffResponse,
    status_code=200,
)
def list_public_staff_for_service_by_slug(
    slug: str,
    service_id: uuid.UUID,
    catalog: PublicCatalogServiceDep,
) -> PublicCatalogStaffResponse:
    result = catalog.list_bookable_staff_for_service_by_slug(
        slug=slug,
        service_id=service_id,
    )
    return PublicCatalogStaffResponse(
        salon_id=result.salon_id,
        service_id=result.service_id,
        staff=[
            PublicCatalogStaffOut(
                id=member.id,
                display_name=member.display_name,
                avatar_media_id=member.avatar_media_id,
            )
            for member in result.staff
        ],
    )


@router.get(
    "/public/salons/{slug}/availability/service",
    response_model=ServiceAvailabilityResponse,
    status_code=200,
)
def get_public_service_availability_by_slug(
    slug: str,
    service_id: uuid.UUID,
    start_date: date,
    end_date: date,
    as_of: AsOfDep,
    catalog: PublicCatalogServiceDep,
    staff_id: uuid.UUID | None = None,
) -> ServiceAvailabilityResponse:
    result = catalog.get_service_availability_by_slug(
        slug=slug,
        service_id=service_id,
        start_date=start_date,
        end_date=end_date,
        staff_id=staff_id,
        as_of=as_of,
    )
    return _to_service_availability_response(result)


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
        manage_token=result.manage_token,
    )


@router.post(
    "/public/salons/{slug}/bookings/{booking_id}/cancel",
    response_model=PublicBookingCancelResponse,
    status_code=200,
)
def cancel_public_booking_by_slug(
    slug: str,
    booking_id: uuid.UUID,
    body: PublicBookingCancelRequest,
    as_of: AsOfDep,
    salon_public_service: SalonPublicServiceDep,
    booking_service: BookingServiceDep,
) -> PublicBookingCancelResponse:
    entry = salon_public_service.resolve_public_salon_by_slug(slug)
    result = booking_service.cancel_booking(
        salon_id=entry.salon_id,
        booking_id=booking_id,
        token=body.token,
        reason=body.reason,
        as_of=as_of,
    )
    return PublicBookingCancelResponse(
        booking_id=result.booking_id,
        status=result.status,
        cancelled_at=result.cancelled_at,
    )
