from __future__ import annotations

from app.core.config import Settings
from app.services.media.errors import MediaValidationError
from app.services.media.storage.base import StorageProvider
from app.services.media.storage.local import LocalStorageProvider


def get_storage_provider(settings: Settings) -> StorageProvider:
    backend = settings.media_storage_backend.strip().lower()
    if backend == "local":
        return LocalStorageProvider(settings.media_storage_root)
    raise MediaValidationError(f"unsupported media storage backend: {backend}")
