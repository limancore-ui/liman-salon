from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.media.types import MediaEntityType, MediaPurpose


class MediaAttachmentResponse(BaseModel):
    id: UUID
    entity_type: str
    entity_id: UUID
    purpose: str
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaAssetResponse(BaseModel):
    id: UUID
    salon_id: UUID
    original_filename: str
    content_type: str
    byte_size: int
    checksum_sha256: str | None
    width_px: int | None
    height_px: int | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MediaAssetDetailResponse(MediaAssetResponse):
    attachments: list[MediaAttachmentResponse] = Field(default_factory=list)


class MediaAttachRequest(BaseModel):
    entity_type: MediaEntityType
    entity_id: UUID
    purpose: MediaPurpose
    sort_order: int = Field(default=0, ge=0)


class MediaAttachmentIndexItemResponse(BaseModel):
    media_id: UUID
    attachment_id: UUID
    filename: str
    entity_type: str
    entity_id: UUID
    purpose: str
