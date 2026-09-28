from __future__ import annotations

import uuid
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.api.deps import get_media_service, get_salon_public_service
from app.db.models.media_asset import MediaAsset
from app.db.models.media_attachment import MediaAttachment
from app.main import create_app
from app.services.media.errors import MediaNotFoundError
from app.services.media.service import MediaService
from app.services.media.types import MediaEntityType, MediaPurpose
from app.services.salon_public.errors import PublicSalonNotFoundError
from app.services.salon_public.service import SalonPublicService
from app.services.salon_public.types import PublicSalonEntry

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
MEDIA_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
SERVICE_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
STAFF_ID = uuid.UUID("ffffffff-ffff-4fff-8fff-ffffffffffff")
CHECKSUM = "a" * 64
NOW = datetime.now(timezone.utc)
_MIN_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
SLUG = "liman-demo"
PUBLIC_PATH = f"/api/v1/public/salons/{SLUG}/media/{MEDIA_ID}/content"


class _MemoryStorage:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def open(self, *, key: str) -> BytesIO:
        _ = key
        return BytesIO(self._data)


def _entry() -> PublicSalonEntry:
    return PublicSalonEntry(
        salon_id=SALON_A,
        slug=SLUG,
        name="Liman Demo",
        currency_code="KZT",
        timezone="Asia/Almaty",
    )


def _asset_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": MEDIA_ID,
        "salon_id": SALON_A,
        "storage_key": f"{SALON_A}/{MEDIA_ID}/original.jpg",
        "original_filename": "photo.jpg",
        "content_type": "image/jpeg",
        "byte_size": len(_MIN_JPEG),
        "checksum_sha256": CHECKSUM,
        "deleted_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _public_app(
    *,
    mock_salon: MagicMock | None = None,
    mock_media: MagicMock | None = None,
) -> tuple[TestClient, MagicMock, MagicMock]:
    app = create_app()
    salon_svc = mock_salon or MagicMock(spec=SalonPublicService)
    media_svc = mock_media or MagicMock(spec=MediaService)
    app.dependency_overrides[get_salon_public_service] = lambda: salon_svc
    app.dependency_overrides[get_media_service] = lambda: media_svc
    return TestClient(app), salon_svc, media_svc


def _real_media_service(
    *,
    attachments: list[MediaAttachment],
    salon_id: uuid.UUID = SALON_A,
    service_active: bool = True,
    staff_active_bookable: bool = True,
    asset_deleted_at: datetime | None = None,
    asset_salon_id: uuid.UUID = SALON_A,
) -> MediaService:
    storage = _MemoryStorage(_MIN_JPEG)
    session = MagicMock()
    svc = MediaService(session, storage, max_upload_bytes=1024)
    asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=asset_salon_id,
        storage_key=f"{asset_salon_id}/{MEDIA_ID}/original.jpg",
        original_filename="photo.jpg",
        content_type="image/jpeg",
        byte_size=len(_MIN_JPEG),
        checksum_sha256=CHECKSUM,
        deleted_at=asset_deleted_at,
    )

    def get_asset_by_id(
        *,
        salon_id: uuid.UUID,
        media_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> MediaAsset | None:
        if media_id != MEDIA_ID:
            return None
        if asset.salon_id != salon_id:
            return None
        if asset.deleted_at is not None and not include_deleted:
            return None
        return asset

    svc._repo.get_asset_by_id = MagicMock(side_effect=get_asset_by_id)
    svc._repo.list_attachments_for_asset = MagicMock(return_value=attachments)
    svc._repo.service_is_active = MagicMock(return_value=service_active)
    svc._repo.staff_is_active_bookable = MagicMock(return_value=staff_active_bookable)
    return svc


def _attachment(
    *,
    entity_type: MediaEntityType,
    entity_id: uuid.UUID,
    purpose: MediaPurpose,
) -> MediaAttachment:
    return MediaAttachment(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
        entity_type=entity_type.value,
        entity_id=entity_id,
        purpose=purpose.value,
        sort_order=0,
    )


def test_valid_public_media_content_streams() -> None:
    client, salon_svc, media_svc = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    media_svc.open_public_asset_content.return_value = (
        _asset_row(),
        BytesIO(_MIN_JPEG),
    )
    try:
        response = client.get(PUBLIC_PATH)
        assert response.status_code == 200
        assert response.content == _MIN_JPEG
        assert response.headers["content-type"].startswith("image/jpeg")
        salon_svc.resolve_public_salon_by_slug.assert_called_once_with(SLUG)
        media_svc.open_public_asset_content.assert_called_once_with(
            salon_id=SALON_A,
            media_id=MEDIA_ID,
        )
    finally:
        client.close()


def test_public_media_no_auth_required() -> None:
    client, salon_svc, media_svc = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    media_svc.open_public_asset_content.return_value = (
        _asset_row(),
        BytesIO(_MIN_JPEG),
    )
    try:
        assert client.get(PUBLIC_PATH).status_code == 200
    finally:
        client.close()


def test_inactive_salon_404() -> None:
    client, salon_svc, media_svc = _public_app()
    salon_svc.resolve_public_salon_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    media_svc.open_public_asset_content.assert_not_called()


def test_missing_media_404() -> None:
    client, salon_svc, media_svc = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    media_svc.open_public_asset_content.side_effect = MediaNotFoundError(
        "media asset not found"
    )
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert "salon" not in response.json()["detail"].lower()


def test_media_belonging_to_another_salon_404() -> None:
    client, salon_svc, _media_svc = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.SALON,
                entity_id=SALON_B,
                purpose=MediaPurpose.LOGO,
            )
        ],
        asset_salon_id=SALON_B,
    )
    app = client.app
    app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_soft_deleted_media_404() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.SALON,
                entity_id=SALON_A,
                purpose=MediaPurpose.LOGO,
            )
        ],
        asset_deleted_at=NOW,
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_unattached_media_404() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(attachments=[])
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_attachment_to_inactive_service_404() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.SERVICE,
                entity_id=SERVICE_ID,
                purpose=MediaPurpose.COVER,
            )
        ],
        service_active=False,
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404


def test_attachment_to_inactive_staff_404() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.STAFF,
                entity_id=STAFF_ID,
                purpose=MediaPurpose.AVATAR,
            )
        ],
        staff_active_bookable=False,
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404


def test_allowed_salon_logo_streams() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.SALON,
                entity_id=SALON_A,
                purpose=MediaPurpose.LOGO,
            )
        ],
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 200
    assert response.content == _MIN_JPEG


def test_allowed_service_cover_streams() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.SERVICE,
                entity_id=SERVICE_ID,
                purpose=MediaPurpose.COVER,
            )
        ],
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 200
    assert response.content == _MIN_JPEG


def test_allowed_staff_avatar_streams() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.STAFF,
                entity_id=STAFF_ID,
                purpose=MediaPurpose.AVATAR,
            )
        ],
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 200
    assert response.content == _MIN_JPEG


def test_content_type_and_cache_headers() -> None:
    client, salon_svc, media_svc = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    media_svc.open_public_asset_content.return_value = (
        _asset_row(content_type="image/png", checksum_sha256=CHECKSUM),
        BytesIO(_MIN_JPEG),
    )
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["etag"] == f'"{CHECKSUM}"'


def test_gallery_attachment_not_public_404() -> None:
    client, salon_svc, _ = _public_app()
    salon_svc.resolve_public_salon_by_slug.return_value = _entry()
    real = _real_media_service(
        attachments=[
            _attachment(
                entity_type=MediaEntityType.SERVICE,
                entity_id=SERVICE_ID,
                purpose=MediaPurpose.GALLERY,
            )
        ],
    )
    client.app.dependency_overrides[get_media_service] = lambda: real
    response = client.get(PUBLIC_PATH)
    assert response.status_code == 404
