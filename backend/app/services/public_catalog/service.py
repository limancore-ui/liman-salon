from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.services.media.repository import MediaRepository
from app.services.media.types import MediaEntityType, MediaPurpose
from app.services.availability.repository import AvailabilityRepository
from app.services.availability.service import AvailabilityService
from app.services.availability.types import ServiceAvailabilityResult
from app.services.public_catalog.types import (
    PublicCatalogServiceItem,
    PublicCatalogServicesResult,
    PublicCatalogStaffMember,
    PublicCatalogStaffResult,
)
from app.services.salon_public.service import SalonPublicService
from app.services.service_catalog.errors import ServiceCatalogNotFoundError
from app.services.service_catalog.service import ServiceCatalogService
from app.services.public_catalog.availability_validation import (
    validate_public_service_availability_date_range,
)
from app.services.staff.repository import StaffRepository


class PublicCatalogService:
    """Slug-based public catalog reads; composes existing tenant-scoped services."""

    def __init__(self, session: Session) -> None:
        self._salon_public = SalonPublicService(session)
        self._catalog = ServiceCatalogService(session)
        self._availability = AvailabilityService(session)
        self._availability_repo = AvailabilityRepository(session)
        self._staff_repo = StaffRepository(session)
        self._media_repo = MediaRepository(session)

    def list_active_services_by_slug(self, slug: str) -> PublicCatalogServicesResult:
        entry = self._salon_public.resolve_public_salon_by_slug(slug)
        rows = self._catalog.list_services(salon_id=entry.salon_id, active_only=True)
        services = tuple(
            PublicCatalogServiceItem(
                id=row.id,
                name=row.name,
                description=row.description,
                duration_minutes=row.duration_minutes,
                buffer_before_minutes=row.buffer_before_minutes,
                buffer_after_minutes=row.buffer_after_minutes,
                price_cents=row.price_cents,
                currency_code=entry.currency_code,
                cover_media_id=self._media_repo.resolve_attached_media_id(
                    salon_id=entry.salon_id,
                    entity_type=MediaEntityType.SERVICE,
                    entity_id=row.id,
                    purpose=MediaPurpose.COVER,
                ),
            )
            for row in rows
        )
        return PublicCatalogServicesResult(salon_id=entry.salon_id, services=services)

    def list_bookable_staff_for_service_by_slug(
        self,
        *,
        slug: str,
        service_id: uuid.UUID,
    ) -> PublicCatalogStaffResult:
        entry = self._salon_public.resolve_public_salon_by_slug(slug)
        salon_id = entry.salon_id
        active = self._availability_repo.get_active_service_for_availability(
            salon_id, service_id
        )
        if active is None:
            raise ServiceCatalogNotFoundError("service not found")

        staff_ids = self._availability_repo.list_bookable_staff_for_service(
            salon_id, service_id
        )
        members: list[PublicCatalogStaffMember] = []
        for staff_id in staff_ids:
            row = self._staff_repo.get_staff_by_id(
                salon_id=salon_id, staff_id=staff_id
            )
            if row is None:
                continue
            members.append(
                PublicCatalogStaffMember(
                    id=row.id,
                    display_name=row.display_name,
                    avatar_media_id=self._media_repo.resolve_attached_media_id(
                        salon_id=salon_id,
                        entity_type=MediaEntityType.STAFF,
                        entity_id=row.id,
                        purpose=MediaPurpose.AVATAR,
                    ),
                )
            )
        return PublicCatalogStaffResult(
            salon_id=salon_id,
            service_id=service_id,
            staff=tuple(members),
        )

    def get_service_availability_by_slug(
        self,
        *,
        slug: str,
        service_id: uuid.UUID,
        start_date: date,
        end_date: date,
        as_of: datetime,
        staff_id: uuid.UUID | None = None,
    ) -> ServiceAvailabilityResult:
        entry = self._salon_public.resolve_public_salon_by_slug(slug)
        validate_public_service_availability_date_range(start_date, end_date)
        return self._availability.get_service_availability(
            salon_id=entry.salon_id,
            service_id=service_id,
            start_date=start_date,
            end_date=end_date,
            staff_id=staff_id,
            as_of=as_of,
        )
