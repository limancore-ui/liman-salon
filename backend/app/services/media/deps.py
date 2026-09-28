from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.media.service import MediaService
from app.services.media.storage.factory import get_storage_provider


def build_media_service(session: Session) -> MediaService:
    settings = get_settings()
    return MediaService(
        session,
        get_storage_provider(settings),
        max_upload_bytes=settings.media_max_upload_bytes,
    )
