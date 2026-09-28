from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.db.models.media_asset import MediaAsset
from app.db.models.media_attachment import MediaAttachment
from app.services.media.repository import MediaRepository
from app.services.media.service import MediaService
from app.services.media.types import MediaEntityType, MediaPurpose

SALON_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MEDIA_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
ATTACHMENT_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
SERVICE_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
NOW = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)


def test_service_list_attachment_index_maps_repo_rows() -> None:
    session = MagicMock()
    service = MediaService(session, MagicMock(), max_upload_bytes=1024)
    attachment = MediaAttachment(
        id=ATTACHMENT_ID,
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
        entity_type=MediaEntityType.SERVICE.value,
        entity_id=SERVICE_ID,
        purpose=MediaPurpose.COVER.value,
        sort_order=0,
        created_at=NOW,
    )
    asset = MediaAsset(
        id=MEDIA_ID,
        salon_id=SALON_A,
        storage_key=f"{SALON_A}/{MEDIA_ID}/original.jpg",
        original_filename="cover.jpg",
        content_type="image/jpeg",
        byte_size=100,
        created_at=NOW,
        updated_at=NOW,
    )
    service._repo.list_attachment_index = MagicMock(return_value=[(attachment, asset)])

    items = service.list_attachment_index(salon_id=SALON_A)

    assert len(items) == 1
    row = items[0]
    assert row.media_id == MEDIA_ID
    assert row.attachment_id == ATTACHMENT_ID
    assert row.filename == "cover.jpg"
    assert row.entity_type == "service"
    assert row.entity_id == SERVICE_ID
    assert row.purpose == "cover"
    service._repo.list_attachment_index.assert_called_once_with(salon_id=SALON_A)


def test_repository_list_attachment_index_query_filters_deleted() -> None:
    session = MagicMock()
    repo = MediaRepository(session)
    repo.list_attachment_index(salon_id=SALON_A)
    session.execute.assert_called_once()
    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "deleted_at IS NULL" in compiled or "deleted_at IS" in compiled
    assert "media_attachments" in compiled.lower() or "media_attachment" in compiled.lower()
