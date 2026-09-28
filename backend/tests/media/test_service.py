from __future__ import annotations

import uuid
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.media_asset import MediaAsset
from app.db.models.media_attachment import MediaAttachment
from app.services.media.errors import MediaConflictError, MediaNotFoundError, MediaValidationError
from app.services.media.service import MediaService
from app.services.media.types import MediaAttachInput, MediaEntityType, MediaPurpose, MediaUploadInput

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SALON_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
MEDIA_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
SERVICE_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
_MIN_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


class _MemoryStorage:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put(self, *, key: str, data: bytes, content_type: str) -> None:
        _ = content_type
        self._objects[key] = data

    def open(self, *, key: str) -> BytesIO:
        return BytesIO(self._objects[key])

    def delete(self, *, key: str) -> None:
        self.deleted.append(key)
        self._objects.pop(key, None)

    def exists(self, *, key: str) -> bool:
        return key in self._objects


def _svc(storage: _MemoryStorage | None = None) -> tuple[MediaService, _MemoryStorage, MagicMock]:
    storage = storage or _MemoryStorage()
    session = MagicMock()
    service = MediaService(session, storage, max_upload_bytes=1024)
    return service, storage, session


def test_build_storage_key_uses_salon_asset_and_extension() -> None:
    asset_id = uuid.uuid4()
    key = MediaService.build_storage_key(
        salon_id=SALON_A,
        asset_id=asset_id,
        content_type="image/jpeg",
    )
    assert key == f"{SALON_A}/{asset_id}/original.jpg"


def test_upload_persists_asset_and_bytes() -> None:
    svc, storage, _session = _svc()
    svc._repo.add_asset = MagicMock(side_effect=lambda asset: asset)

    asset = svc.upload_asset(
        salon_id=SALON_A,
        upload=MediaUploadInput(
            original_filename="photo.jpg",
            content_type="image/jpeg",
            data=_MIN_JPEG,
        ),
    )

    assert asset.salon_id == SALON_A
    assert asset.byte_size == len(_MIN_JPEG)
    assert storage.exists(key=asset.storage_key)
    svc._repo.add_asset.assert_called_once()


def test_upload_rolls_back_storage_on_db_failure() -> None:
    svc, storage, _session = _svc()
    svc._repo.add_asset = MagicMock(side_effect=RuntimeError("db down"))

    with pytest.raises(RuntimeError):
        svc.upload_asset(
            salon_id=SALON_A,
            upload=MediaUploadInput(
                original_filename="photo.jpg",
                content_type="image/jpeg",
                data=_MIN_JPEG,
            ),
        )

    assert len(storage._objects) == 0
    assert len(storage.deleted) == 1


def test_get_asset_enforces_tenant_scope() -> None:
    svc, _storage, _session = _svc()
    other_salon_asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=SALON_B,
        storage_key="k",
        original_filename="x.jpg",
        content_type="image/jpeg",
        byte_size=10,
    )
    svc._repo.get_asset_by_id = MagicMock(return_value=other_salon_asset)

    found = svc.get_asset(salon_id=SALON_B, media_id=MEDIA_ID)
    assert found.salon_id == SALON_B
    svc._repo.get_asset_by_id.assert_called_with(
        salon_id=SALON_B,
        media_id=MEDIA_ID,
        include_deleted=False,
    )

    svc._repo.get_asset_by_id = MagicMock(return_value=None)
    with pytest.raises(MediaNotFoundError):
        svc.get_asset(salon_id=SALON_A, media_id=MEDIA_ID)


def test_soft_delete_marks_row_and_removes_bytes() -> None:
    svc, storage, _session = _svc()
    asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=SALON_A,
        storage_key=f"{SALON_A}/{MEDIA_ID}/original.jpg",
        original_filename="photo.jpg",
        content_type="image/jpeg",
        byte_size=len(_MIN_JPEG),
    )
    storage.put(key=asset.storage_key, data=_MIN_JPEG, content_type="image/jpeg")
    svc._repo.get_asset_by_id = MagicMock(return_value=asset)
    svc._repo.soft_delete_asset = MagicMock()
    svc._repo.delete_attachments_for_asset = MagicMock()

    svc.soft_delete_asset(salon_id=SALON_A, media_id=MEDIA_ID, clock=lambda: NOW)

    svc._repo.soft_delete_asset.assert_called_once_with(asset, deleted_at=NOW)
    svc._repo.delete_attachments_for_asset.assert_called_once()
    assert not storage.exists(key=asset.storage_key)


def test_attach_cover_replaces_existing_unique_attachment() -> None:
    svc, _storage, _session = _svc()
    asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=SALON_A,
        storage_key="k",
        original_filename="c.jpg",
        content_type="image/jpeg",
        byte_size=10,
    )
    existing = MediaAttachment(
        salon_id=SALON_A,
        media_asset_id=uuid.uuid4(),
        entity_type="service",
        entity_id=SERVICE_ID,
        purpose="cover",
    )
    svc._repo.get_asset_by_id = MagicMock(return_value=asset)
    svc._repo.service_exists = MagicMock(return_value=True)
    svc._repo.find_unique_attachment = MagicMock(return_value=existing)
    svc._repo.delete_attachment = MagicMock()
    svc._repo.add_attachment = MagicMock(side_effect=lambda row: row)

    attachment = svc.attach_asset(
        salon_id=SALON_A,
        media_id=MEDIA_ID,
        data=MediaAttachInput(
            entity_type=MediaEntityType.SERVICE,
            entity_id=SERVICE_ID,
            purpose=MediaPurpose.COVER,
        ),
    )

    svc._repo.delete_attachment.assert_called_once_with(existing)
    assert attachment.purpose == "cover"
    assert attachment.entity_id == SERVICE_ID


def test_attach_salon_logo_requires_matching_entity_id() -> None:
    svc, _storage, _session = _svc()
    asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=SALON_A,
        storage_key="k",
        original_filename="logo.png",
        content_type="image/png",
        byte_size=10,
    )
    svc._repo.get_asset_by_id = MagicMock(return_value=asset)
    svc._repo.find_unique_attachment = MagicMock(return_value=None)
    svc._repo.add_attachment = MagicMock(side_effect=lambda row: row)

    with pytest.raises(MediaValidationError):
        svc.attach_asset(
            salon_id=SALON_A,
            media_id=MEDIA_ID,
            data=MediaAttachInput(
                entity_type=MediaEntityType.SALON,
                entity_id=SALON_B,
                purpose=MediaPurpose.LOGO,
            ),
        )


def test_attach_integrity_error_surfaces_conflict_when_retry_fails() -> None:
    svc, _storage, _session = _svc()
    asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=SALON_A,
        storage_key="k",
        original_filename="c.jpg",
        content_type="image/jpeg",
        byte_size=10,
    )
    svc._repo.get_asset_by_id = MagicMock(return_value=asset)
    svc._repo.service_exists = MagicMock(return_value=True)
    svc._repo.find_unique_attachment = MagicMock(return_value=None)
    svc._repo.add_attachment = MagicMock(side_effect=IntegrityError("insert", {}, Exception()))

    with pytest.raises(MediaConflictError):
        svc.attach_asset(
            salon_id=SALON_A,
            media_id=MEDIA_ID,
            data=MediaAttachInput(
                entity_type=MediaEntityType.SERVICE,
                entity_id=SERVICE_ID,
                purpose=MediaPurpose.GALLERY,
            ),
        )
