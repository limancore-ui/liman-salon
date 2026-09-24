from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SalonPublicServiceDep
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
