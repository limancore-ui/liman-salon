from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class MediaEntityType(StrEnum):
    SALON = "salon"
    SERVICE = "service"
    STAFF = "staff"


class MediaPurpose(StrEnum):
    LOGO = "logo"
    COVER = "cover"
    AVATAR = "avatar"
    GALLERY = "gallery"


DEFAULT_ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
)

CONTENT_TYPE_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

UNIQUE_ATTACHMENT_PURPOSES: frozenset[MediaPurpose] = frozenset(
    {
        MediaPurpose.LOGO,
        MediaPurpose.COVER,
        MediaPurpose.AVATAR,
    }
)


@dataclass(frozen=True, slots=True)
class MediaUploadInput:
    original_filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True, slots=True)
class MediaAttachInput:
    entity_type: MediaEntityType
    entity_id: UUID
    purpose: MediaPurpose
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class MediaAssetSummary:
    id: UUID
    salon_id: UUID
    original_filename: str
    content_type: str
    byte_size: int
    created_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class MediaAttachmentIndexItem:
    media_id: UUID
    attachment_id: UUID
    filename: str
    entity_type: str
    entity_id: UUID
    purpose: str
