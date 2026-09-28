from __future__ import annotations

import uuid
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_media_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.media.errors import MediaNotFoundError, MediaValidationError
from app.services.media.service import MediaService
from app.services.media.types import (
    MediaAttachmentIndexItem,
    MediaEntityType,
    MediaPurpose,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MEDIA_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
ATTACHMENT_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
NOW = datetime.now(timezone.utc)
_MIN_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32


def _media_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": MEDIA_ID,
        "salon_id": SALON_A,
        "storage_key": f"{SALON_A}/{MEDIA_ID}/original.jpg",
        "original_filename": "photo.jpg",
        "content_type": "image/jpeg",
        "byte_size": len(_MIN_JPEG),
        "checksum_sha256": "abc" * 21 + "a",
        "width_px": None,
        "height_px": None,
        "created_by_user_id": USER_ID,
        "created_at": NOW,
        "updated_at": NOW,
        "deleted_at": None,
        "attachments": [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _attachment_row(**kwargs: object) -> SimpleNamespace:
    defaults = {
        "id": ATTACHMENT_ID,
        "salon_id": SALON_A,
        "media_asset_id": MEDIA_ID,
        "entity_type": MediaEntityType.SALON.value,
        "entity_id": SALON_A,
        "purpose": MediaPurpose.LOGO.value,
        "sort_order": 0,
        "created_at": NOW,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _auth_app(
    *,
    role: str = "owner",
    salon_id: uuid.UUID = SALON_A,
) -> tuple[TestClient, MagicMock, dict[str, str]]:
    app = create_app()
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=salon_id,
        name="Salon",
        slug="salon",
        is_active=True,
    )
    mock_auth.get_active_membership.return_value = SimpleNamespace(
        salon_id=salon_id,
        user_id=USER_ID,
        role=role,
        is_active=True,
    )
    mock_media = MagicMock(spec=MediaService)
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    app.dependency_overrides[get_media_service] = lambda: mock_media
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, mock_media, headers


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_list_media_read_roles(role: str) -> None:
    client, mock_media, headers = _auth_app(role=role)
    mock_media.list_assets.return_value = [_media_row()]
    try:
        response = client.get(f"/api/v1/salons/{SALON_A}/media", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert "storage_key" not in body[0]
        mock_media.list_assets.assert_called_once_with(
            salon_id=SALON_A,
            limit=50,
            offset=0,
        )
    finally:
        client.close()


def test_list_media_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert client.get(f"/api/v1/salons/{SALON_A}/media").status_code == 401


def test_get_media_detail_tenant_scoped() -> None:
    client, mock_media, headers = _auth_app()
    mock_media.get_asset.return_value = _media_row(
        attachments=[_attachment_row()],
    )
    response = client.get(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(MEDIA_ID)
    assert "storage_key" not in data
    assert len(data["attachments"]) == 1
    mock_media.get_asset.assert_called_once_with(salon_id=SALON_A, media_id=MEDIA_ID)


def test_get_media_not_found_404() -> None:
    client, mock_media, headers = _auth_app()
    mock_media.get_asset.side_effect = MediaNotFoundError("media asset not found")
    response = client.get(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}",
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_owner_can_upload() -> None:
    client, mock_media, headers = _auth_app(role="owner")
    mock_media.upload_asset.return_value = _media_row()
    response = client.post(
        f"/api/v1/salons/{SALON_A}/media",
        headers=headers,
        files={"file": ("photo.jpg", _MIN_JPEG, "image/jpeg")},
    )
    assert response.status_code == 201
    assert "storage_key" not in response.json()
    call = mock_media.upload_asset.call_args.kwargs
    assert call["salon_id"] == SALON_A
    assert call["created_by_user_id"] == USER_ID
    assert call["upload"].content_type == "image/jpeg"


@pytest.mark.parametrize("role", ["staff", "receptionist"])
def test_upload_forbidden_for_non_admin(role: str) -> None:
    client, mock_media, headers = _auth_app(role=role)
    response = client.post(
        f"/api/v1/salons/{SALON_A}/media",
        headers=headers,
        files={"file": ("photo.jpg", _MIN_JPEG, "image/jpeg")},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    mock_media.upload_asset.assert_not_called()


def test_upload_invalid_mime_422() -> None:
    client, mock_media, headers = _auth_app(role="owner")
    mock_media.upload_asset.side_effect = MediaValidationError("unsupported content type")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/media",
        headers=headers,
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_upload_oversized_422() -> None:
    client, mock_media, headers = _auth_app(role="owner")
    mock_media.upload_asset.side_effect = MediaValidationError("upload exceeds maximum size")
    response = client.post(
        f"/api/v1/salons/{SALON_A}/media",
        headers=headers,
        files={"file": ("big.jpg", _MIN_JPEG, "image/jpeg")},
    )
    assert response.status_code == 422


def test_owner_can_delete() -> None:
    client, mock_media, headers = _auth_app(role="owner")
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}",
        headers=headers,
    )
    assert response.status_code == 204
    assert mock_media.soft_delete_asset.call_args.kwargs["salon_id"] == SALON_A


def test_staff_cannot_delete_403() -> None:
    client, mock_media, headers = _auth_app(role="staff")
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}",
        headers=headers,
    )
    assert response.status_code == 403
    mock_media.soft_delete_asset.assert_not_called()


def test_get_media_content_streams_bytes() -> None:
    client, mock_media, headers = _auth_app(role="staff")
    mock_media.get_asset.return_value = _media_row()
    mock_media.open_asset_content.return_value = BytesIO(_MIN_JPEG)
    response = client.get(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}/content",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.content == _MIN_JPEG
    assert response.headers["content-type"].startswith("image/jpeg")


def test_attach_media_owner() -> None:
    client, mock_media, headers = _auth_app(role="owner")
    mock_media.attach_asset.return_value = _attachment_row()
    response = client.put(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}/attachments",
        headers=headers,
        json={
            "entity_type": "salon",
            "entity_id": str(SALON_A),
            "purpose": "logo",
            "sort_order": 0,
        },
    )
    assert response.status_code == 200
    assert mock_media.attach_asset.call_args.kwargs["salon_id"] == SALON_A


def test_staff_cannot_attach_403() -> None:
    client, mock_media, headers = _auth_app(role="staff")
    response = client.put(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}/attachments",
        headers=headers,
        json={
            "entity_type": "salon",
            "entity_id": str(SALON_A),
            "purpose": "logo",
        },
    )
    assert response.status_code == 403
    mock_media.attach_asset.assert_not_called()


def test_detach_attachment_owner() -> None:
    client, mock_media, headers = _auth_app(role="admin")
    response = client.delete(
        f"/api/v1/salons/{SALON_A}/media/{MEDIA_ID}/attachments/{ATTACHMENT_ID}",
        headers=headers,
    )
    assert response.status_code == 204
    mock_media.detach_attachment.assert_called_once_with(
        salon_id=SALON_A,
        media_id=MEDIA_ID,
        attachment_id=ATTACHMENT_ID,
    )


def _index_item(**kwargs: object) -> MediaAttachmentIndexItem:
    defaults = {
        "media_id": MEDIA_ID,
        "attachment_id": ATTACHMENT_ID,
        "filename": "photo.jpg",
        "entity_type": MediaEntityType.SALON.value,
        "entity_id": SALON_A,
        "purpose": MediaPurpose.LOGO.value,
    }
    defaults.update(kwargs)
    return MediaAttachmentIndexItem(
        media_id=defaults["media_id"],  # type: ignore[arg-type]
        attachment_id=defaults["attachment_id"],  # type: ignore[arg-type]
        filename=defaults["filename"],  # type: ignore[arg-type]
        entity_type=defaults["entity_type"],  # type: ignore[arg-type]
        entity_id=defaults["entity_id"],  # type: ignore[arg-type]
        purpose=defaults["purpose"],  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("role", ["owner", "admin", "staff", "receptionist"])
def test_attachment_index_read_roles(role: str) -> None:
    client, mock_media, headers = _auth_app(role=role)
    mock_media.list_attachment_index.return_value = [_index_item()]
    try:
        response = client.get(
            f"/api/v1/salons/{SALON_A}/media/attachments/index",
            headers=headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        row = body[0]
        assert row["media_id"] == str(MEDIA_ID)
        assert row["attachment_id"] == str(ATTACHMENT_ID)
        assert row["filename"] == "photo.jpg"
        assert row["purpose"] == "logo"
        assert "storage_key" not in row
        mock_media.list_attachment_index.assert_called_once_with(salon_id=SALON_A)
    finally:
        client.close()


def test_attachment_index_unauthenticated() -> None:
    app = create_app()
    with TestClient(app) as client:
        assert (
            client.get(f"/api/v1/salons/{SALON_A}/media/attachments/index").status_code
            == 401
        )


def test_attachment_index_includes_cover_and_avatar() -> None:
    client, mock_media, headers = _auth_app()
    service_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
    staff_id = uuid.UUID("22222222-2222-4222-8222-222222222222")
    mock_media.list_attachment_index.return_value = [
        _index_item(
            entity_type=MediaEntityType.SERVICE.value,
            entity_id=service_id,
            purpose=MediaPurpose.COVER.value,
            filename="cover.webp",
        ),
        _index_item(
            attachment_id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
            entity_type=MediaEntityType.STAFF.value,
            entity_id=staff_id,
            purpose=MediaPurpose.AVATAR.value,
            filename="avatar.png",
        ),
        _index_item(),
    ]
    response = client.get(
        f"/api/v1/salons/{SALON_A}/media/attachments/index",
        headers=headers,
    )
    assert response.status_code == 200
    purposes = {row["purpose"] for row in response.json()}
    assert purposes == {"cover", "avatar", "logo"}


def test_attachment_index_tenant_scoped_via_context() -> None:
    client, mock_media, headers = _auth_app(role="owner", salon_id=SALON_A)
    response = client.get(
        f"/api/v1/salons/{SALON_A}/media/attachments/index",
        headers=headers,
    )
    assert response.status_code == 200
    mock_media.list_attachment_index.assert_called_with(salon_id=SALON_A)


def test_attachment_index_salon_b_without_membership_403() -> None:
    client, mock_media, headers = _auth_app(role="owner", salon_id=SALON_A)
    app = client.app
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="o@e.com",
        full_name="O",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B, name="B", slug="b", is_active=True
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    r = client.get(
        f"/api/v1/salons/{SALON_B}/media/attachments/index",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    mock_media.list_attachment_index.assert_not_called()


def test_cannot_access_salon_b_without_membership() -> None:
    client, mock_media, headers = _auth_app(role="owner", salon_id=SALON_A)
    app = client.app
    mock_auth = MagicMock()
    mock_auth.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="o@e.com",
        full_name="O",
        is_active=True,
    )
    mock_auth.get_active_salon.return_value = SimpleNamespace(
        id=SALON_B, name="B", slug="b", is_active=True
    )
    mock_auth.get_active_membership.return_value = None
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    r = client.get(
        f"/api/v1/salons/{SALON_B}/media",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    mock_media.list_assets.assert_not_called()
