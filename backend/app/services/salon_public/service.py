from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.media.repository import MediaRepository
from app.services.media.types import MediaEntityType, MediaPurpose
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.repository import SalonPublicRepository
from app.services.salon_public.slug import normalize_salon_slug
from app.services.salon_public.types import PublicSalonEntry


class SalonPublicService:
    def __init__(self, session: Session) -> None:
        self._repo = SalonPublicRepository(session)
        self._media_repo = MediaRepository(session)

    def resolve_public_salon_by_slug(self, slug: str) -> PublicSalonEntry:
        normalized = normalize_salon_slug(slug)
        salon = self._repo.get_active_salon_by_slug(normalized)
        if salon is None:
            raise PublicSalonNotFoundError("salon not found")
        logo_media_id = self._media_repo.resolve_attached_media_id(
            salon_id=salon.id,
            entity_type=MediaEntityType.SALON,
            entity_id=salon.id,
            purpose=MediaPurpose.LOGO,
        )
        return PublicSalonEntry(
            salon_id=salon.id,
            slug=salon.slug,
            name=salon.name,
            currency_code=salon.currency_code,
            timezone=salon.timezone,
            logo_media_id=logo_media_id,
        )
