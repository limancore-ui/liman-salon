from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.media_asset import MediaAsset
from app.db.models.media_attachment import MediaAttachment
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.media.types import MediaEntityType, MediaPurpose


class MediaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_assets(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int,
        offset: int,
        include_deleted: bool = False,
    ) -> list[MediaAsset]:
        stmt = select(MediaAsset).where(MediaAsset.salon_id == salon_id)
        if not include_deleted:
            stmt = stmt.where(MediaAsset.deleted_at.is_(None))
        stmt = stmt.order_by(MediaAsset.created_at.desc(), MediaAsset.id.asc())
        stmt = stmt.limit(limit).offset(offset)
        return list(self._session.scalars(stmt).all())

    def get_asset_by_id(
        self,
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> MediaAsset | None:
        stmt = select(MediaAsset).where(
            MediaAsset.salon_id == salon_id,
            MediaAsset.id == media_id,
        )
        if not include_deleted:
            stmt = stmt.where(MediaAsset.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def add_asset(self, asset: MediaAsset) -> MediaAsset:
        self._session.add(asset)
        self._session.flush()
        return asset

    def soft_delete_asset(self, asset: MediaAsset, *, deleted_at: datetime) -> None:
        asset.deleted_at = deleted_at
        self._session.flush()

    def delete_attachments_for_asset(
        self,
        *,
        salon_id: uuid.UUID,
        media_asset_id: uuid.UUID,
    ) -> None:
        self._session.execute(
            delete(MediaAttachment).where(
                MediaAttachment.salon_id == salon_id,
                MediaAttachment.media_asset_id == media_asset_id,
            )
        )
        self._session.flush()

    def get_attachment_by_id(
        self,
        *,
        salon_id: uuid.UUID,
        attachment_id: uuid.UUID,
    ) -> MediaAttachment | None:
        return self._session.scalar(
            select(MediaAttachment).where(
                MediaAttachment.salon_id == salon_id,
                MediaAttachment.id == attachment_id,
            )
        )

    def resolve_attached_media_id(
        self,
        *,
        salon_id: uuid.UUID,
        entity_type: MediaEntityType,
        entity_id: uuid.UUID,
        purpose: MediaPurpose,
    ) -> uuid.UUID | None:
        attachment = self.find_unique_attachment(
            salon_id=salon_id,
            entity_type=entity_type,
            entity_id=entity_id,
            purpose=purpose,
        )
        if attachment is None:
            return None
        asset = self.get_asset_by_id(
            salon_id=salon_id,
            media_id=attachment.media_asset_id,
        )
        if asset is None:
            return None
        return asset.id

    def find_unique_attachment(
        self,
        *,
        salon_id: uuid.UUID,
        entity_type: MediaEntityType,
        entity_id: uuid.UUID,
        purpose: MediaPurpose,
    ) -> MediaAttachment | None:
        stmt = select(MediaAttachment).where(
            MediaAttachment.salon_id == salon_id,
            MediaAttachment.entity_type == entity_type.value,
            MediaAttachment.entity_id == entity_id,
            MediaAttachment.purpose == purpose.value,
        )
        return self._session.scalar(stmt)

    def add_attachment(self, attachment: MediaAttachment) -> MediaAttachment:
        self._session.add(attachment)
        self._session.flush()
        return attachment

    def delete_attachment(self, attachment: MediaAttachment) -> None:
        self._session.delete(attachment)
        self._session.flush()

    def service_exists(self, *, salon_id: uuid.UUID, service_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(Service.id).where(
                    Service.salon_id == salon_id,
                    Service.id == service_id,
                )
            )
            is not None
        )

    def staff_exists(self, *, salon_id: uuid.UUID, staff_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(
                select(Staff.id).where(
                    Staff.salon_id == salon_id,
                    Staff.id == staff_id,
                )
            )
            is not None
        )

    def list_attachments_for_asset(
        self,
        *,
        salon_id: uuid.UUID,
        media_asset_id: uuid.UUID,
    ) -> list[MediaAttachment]:
        stmt = select(MediaAttachment).where(
            MediaAttachment.salon_id == salon_id,
            MediaAttachment.media_asset_id == media_asset_id,
        )
        return list(self._session.scalars(stmt).all())

    def list_attachment_index(
        self,
        *,
        salon_id: uuid.UUID,
    ) -> list[tuple[MediaAttachment, MediaAsset]]:
        stmt = (
            select(MediaAttachment, MediaAsset)
            .join(
                MediaAsset,
                (MediaAttachment.media_asset_id == MediaAsset.id)
                & (MediaAttachment.salon_id == MediaAsset.salon_id),
            )
            .where(MediaAttachment.salon_id == salon_id)
            .where(MediaAsset.deleted_at.is_(None))
            .order_by(
                MediaAttachment.entity_type.asc(),
                MediaAttachment.entity_id.asc(),
                MediaAttachment.purpose.asc(),
                MediaAttachment.sort_order.asc(),
                MediaAttachment.id.asc(),
            )
        )
        return list(self._session.execute(stmt).all())

    def service_is_active(
        self, *, salon_id: uuid.UUID, service_id: uuid.UUID
    ) -> bool:
        return (
            self._session.scalar(
                select(Service.id).where(
                    Service.salon_id == salon_id,
                    Service.id == service_id,
                    Service.is_active.is_(True),
                )
            )
            is not None
        )

    def staff_is_active_bookable(
        self, *, salon_id: uuid.UUID, staff_id: uuid.UUID
    ) -> bool:
        return (
            self._session.scalar(
                select(Staff.id).where(
                    Staff.salon_id == salon_id,
                    Staff.id == staff_id,
                    Staff.is_active.is_(True),
                    Staff.is_bookable.is_(True),
                )
            )
            is not None
        )

    def flush(self) -> None:
        self._session.flush()
