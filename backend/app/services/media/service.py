from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.media_asset import MediaAsset
from app.db.models.media_attachment import MediaAttachment
from app.services.media.errors import (
    MediaConflictError,
    MediaNotFoundError,
    MediaStorageError,
    MediaValidationError,
)
from app.services.media.repository import MediaRepository
from app.services.media.storage.base import StorageProvider
from app.services.media.types import (
    DEFAULT_ALLOWED_CONTENT_TYPES,
    MediaAttachInput,
    MediaAttachmentIndexItem,
    MediaEntityType,
    MediaPurpose,
    MediaUploadInput,
    UNIQUE_ATTACHMENT_PURPOSES,
)
from app.services.media.validation import (
    extension_for_content_type,
    sanitize_original_filename,
    validate_upload_payload,
)


class MediaService:
    def __init__(
        self,
        session: Session,
        storage: StorageProvider,
        *,
        max_upload_bytes: int,
        allowed_content_types: frozenset[str] | None = None,
    ) -> None:
        self._session = session
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes
        self._allowed_content_types = (
            allowed_content_types or DEFAULT_ALLOWED_CONTENT_TYPES
        )
        self._repo = MediaRepository(session)

    @staticmethod
    def build_storage_key(
        *,
        salon_id: uuid.UUID,
        asset_id: uuid.UUID,
        content_type: str,
    ) -> str:
        ext = extension_for_content_type(content_type)
        return f"{salon_id}/{asset_id}/original.{ext}"

    def list_attachment_index(
        self,
        *,
        salon_id: uuid.UUID,
    ) -> list[MediaAttachmentIndexItem]:
        rows = self._repo.list_attachment_index(salon_id=salon_id)
        return [
            MediaAttachmentIndexItem(
                media_id=asset.id,
                attachment_id=attachment.id,
                filename=asset.original_filename,
                entity_type=attachment.entity_type,
                entity_id=attachment.entity_id,
                purpose=attachment.purpose,
            )
            for attachment, asset in rows
        ]

    def list_assets(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[MediaAsset]:
        if limit < 1 or limit > 200:
            raise MediaValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise MediaValidationError("offset must be >= 0")
        return self._repo.list_assets(
            salon_id=salon_id,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )

    def get_asset(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> MediaAsset:
        row = self._repo.get_asset_by_id(
            salon_id=salon_id,
            media_id=media_id,
            include_deleted=include_deleted,
        )
        if row is None:
            raise MediaNotFoundError("media asset not found")
        return row

    def upload_asset(
        self,
        *,
        salon_id: uuid.UUID,
        upload: MediaUploadInput,
        created_by_user_id: uuid.UUID | None = None,
    ) -> MediaAsset:
        content_type = validate_upload_payload(
            data=upload.data,
            content_type=upload.content_type,
            max_upload_bytes=self._max_upload_bytes,
            allowed_content_types=self._allowed_content_types,
        )
        asset_id = uuid.uuid4()
        storage_key = self.build_storage_key(
            salon_id=salon_id,
            asset_id=asset_id,
            content_type=content_type,
        )
        checksum = hashlib.sha256(upload.data).hexdigest()
        try:
            self._storage.put(
                key=storage_key,
                data=upload.data,
                content_type=content_type,
            )
        except MediaStorageError:
            raise
        except Exception as exc:
            raise MediaStorageError("failed to store upload") from exc

        asset = MediaAsset(
            id=asset_id,
            salon_id=salon_id,
            storage_key=storage_key,
            original_filename=sanitize_original_filename(upload.original_filename),
            content_type=content_type,
            byte_size=len(upload.data),
            checksum_sha256=checksum,
            created_by_user_id=created_by_user_id,
        )
        try:
            return self._repo.add_asset(asset)
        except Exception:
            try:
                self._storage.delete(key=storage_key)
            except MediaStorageError:
                pass
            raise

    def soft_delete_asset(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
        clock: Callable[[], datetime],
    ) -> None:
        asset = self.get_asset(salon_id=salon_id, media_id=media_id)
        self._repo.soft_delete_asset(asset, deleted_at=clock())
        self._repo.delete_attachments_for_asset(
            salon_id=salon_id,
            media_asset_id=asset.id,
        )
        try:
            self._storage.delete(key=asset.storage_key)
        except MediaStorageError as exc:
            raise MediaStorageError("failed to remove stored media") from exc

    def attach_asset(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
        data: MediaAttachInput,
    ) -> MediaAttachment:
        asset = self.get_asset(salon_id=salon_id, media_id=media_id)
        self._validate_attach_target(
            salon_id=salon_id,
            entity_type=data.entity_type,
            entity_id=data.entity_id,
        )
        if data.purpose in UNIQUE_ATTACHMENT_PURPOSES:
            existing = self._repo.find_unique_attachment(
                salon_id=salon_id,
                entity_type=data.entity_type,
                entity_id=data.entity_id,
                purpose=data.purpose,
            )
            if existing is not None:
                self._repo.delete_attachment(existing)

        attachment = MediaAttachment(
            salon_id=salon_id,
            media_asset_id=asset.id,
            entity_type=data.entity_type.value,
            entity_id=data.entity_id,
            purpose=data.purpose.value,
            sort_order=data.sort_order,
        )
        try:
            return self._repo.add_attachment(attachment)
        except IntegrityError as exc:
            if data.purpose in UNIQUE_ATTACHMENT_PURPOSES:
                existing = self._repo.find_unique_attachment(
                    salon_id=salon_id,
                    entity_type=data.entity_type,
                    entity_id=data.entity_id,
                    purpose=data.purpose,
                )
                if existing is not None:
                    self._repo.delete_attachment(existing)
                    return self._repo.add_attachment(attachment)
            raise MediaConflictError("attachment conflicts with an existing record") from exc

    def detach_attachment(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
        attachment_id: uuid.UUID,
    ) -> None:
        _ = self.get_asset(salon_id=salon_id, media_id=media_id)
        attachment = self._repo.get_attachment_by_id(
            salon_id=salon_id,
            attachment_id=attachment_id,
        )
        if attachment is None or attachment.media_asset_id != media_id:
            raise MediaNotFoundError("attachment not found")
        self._repo.delete_attachment(attachment)

    def open_asset_content(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
    ):
        asset = self.get_asset(salon_id=salon_id, media_id=media_id)
        return self._storage.open(key=asset.storage_key)

    def open_public_asset_content(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
    ):
        asset = self.get_asset(salon_id=salon_id, media_id=media_id)
        attachments = self._repo.list_attachments_for_asset(
            salon_id=salon_id,
            media_asset_id=media_id,
        )
        if not self._has_public_eligible_attachment(
            salon_id=salon_id,
            attachments=attachments,
        ):
            raise MediaNotFoundError("media asset not found")
        stream = self._storage.open(key=asset.storage_key)
        return asset, stream

    def _has_public_eligible_attachment(
        self,
        *,
        salon_id: uuid.UUID,
        attachments: list[MediaAttachment],
    ) -> bool:
        for attachment in attachments:
            entity_type = MediaEntityType(attachment.entity_type)
            purpose = MediaPurpose(attachment.purpose)
            if (
                entity_type is MediaEntityType.SALON
                and purpose is MediaPurpose.LOGO
                and attachment.entity_id == salon_id
            ):
                return True
            if entity_type is MediaEntityType.SERVICE and purpose is MediaPurpose.COVER:
                if self._repo.service_is_active(
                    salon_id=salon_id,
                    service_id=attachment.entity_id,
                ):
                    return True
            if entity_type is MediaEntityType.STAFF and purpose is MediaPurpose.AVATAR:
                if self._repo.staff_is_active_bookable(
                    salon_id=salon_id,
                    staff_id=attachment.entity_id,
                ):
                    return True
        return False

    def _validate_attach_target(
        self,
        *,
        salon_id: uuid.UUID,
        entity_type: MediaEntityType,
        entity_id: uuid.UUID,
    ) -> None:
        if entity_type is MediaEntityType.SALON:
            if entity_id != salon_id:
                raise MediaValidationError("salon attachment entity_id must match salon_id")
            return
        if entity_type is MediaEntityType.SERVICE:
            if not self._repo.service_exists(salon_id=salon_id, service_id=entity_id):
                raise MediaNotFoundError("service not found")
            return
        if entity_type is MediaEntityType.STAFF:
            if not self._repo.staff_exists(salon_id=salon_id, staff_id=entity_id):
                raise MediaNotFoundError("staff not found")
            return
        raise MediaValidationError("unsupported entity type")
