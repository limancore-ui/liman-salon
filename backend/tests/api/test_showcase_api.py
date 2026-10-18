from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_showcase_service
from app.api.deps import get_media_service
from app.auth.deps import get_auth_repository
from app.core.security import create_access_token
from app.main import create_app
from app.services.showcase.errors import (
    ShowcaseItemNotFoundError,
    ShowcaseMediaNotFoundError,
)
from app.services.showcase.service import ShowcaseService
from app.services.showcase.types import (
    PublicShowcaseItem,
    PublicShowcaseImageReference,
    PublicShowcaseItemsResult,
    ShowcaseCategory,
)

SALON_A = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
SALON_B = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ITEM_ID = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
MEDIA_ID = uuid.UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
NOW = datetime.now(timezone.utc)


def _item(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": ITEM_ID,
        "salon_id": SALON_A,
        "category": "work",
        "title": "Example",
        "description": None,
        "price_cents": None,
        "media_asset_id": MEDIA_ID,
        "sort_order": 0,
        "is_published": False,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _client(*, role: str = "owner") -> tuple[TestClient, MagicMock]:
    app = create_app()
    auth_repo = MagicMock()
    auth_repo.get_active_user_by_id.return_value = SimpleNamespace(
        id=USER_ID,
        email="owner@example.com",
        full_name="Owner",
        is_active=True,
    )

    def _salon(salon_id: uuid.UUID) -> SimpleNamespace:
        return SimpleNamespace(
            id=salon_id,
            name="Salon",
            slug="salon-a" if salon_id == SALON_A else "salon-b",
            is_active=True,
            timezone="UTC",
            currency_code="KZT",
        )

    auth_repo.get_active_salon.side_effect = _salon
    auth_repo.get_active_membership.side_effect = lambda salon_id, user_id: (
        SimpleNamespace(
            salon_id=SALON_A,
            user_id=USER_ID,
            role=role,
            is_active=True,
        )
        if salon_id == SALON_A and user_id == USER_ID
        else None
    )
    showcase_service = MagicMock(spec=ShowcaseService)
    app.dependency_overrides[get_auth_repository] = lambda: auth_repo
    app.dependency_overrides[get_showcase_service] = lambda: showcase_service
    token, _ = create_access_token(user_id=USER_ID, now=NOW)
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, showcase_service


def test_admin_list_items_uses_authenticated_salon() -> None:
    client, service = _client(role="staff")
    service.list_items.return_value = [_item()]

    response = client.get(f"/api/v1/salons/{SALON_A}/showcase/items")

    assert response.status_code == 200
    assert response.json()[0]["salon_id"] == str(SALON_A)
    service.list_items.assert_called_once_with(salon_id=SALON_A, limit=50, offset=0)
    client.close()


def test_admin_create_item() -> None:
    client, service = _client()
    service.create_item.return_value = _item(title="Created")

    response = client.post(
        f"/api/v1/salons/{SALON_A}/showcase/items",
        json={
            "category": "cosmetics",
            "title": "Created",
            "media_asset_id": str(MEDIA_ID),
            "price_cents": 1250,
            "sort_order": 2,
        },
    )

    assert response.status_code == 201
    service.create_item.assert_called_once_with(
        salon_id=SALON_A,
        media_asset_id=MEDIA_ID,
        category=ShowcaseCategory.COSMETICS,
        title="Created",
        description=None,
        price_cents=1250,
        sort_order=2,
    )
    client.close()


def test_admin_patch_item_fields() -> None:
    client, service = _client()
    service.update_item.return_value = _item(title="Updated", price_cents=900)

    response = client.patch(
        f"/api/v1/salons/{SALON_A}/showcase/items/{ITEM_ID}",
        json={"title": "Updated", "price_cents": 900},
    )

    assert response.status_code == 200
    service.update_item.assert_called_once_with(
        salon_id=SALON_A,
        item_id=ITEM_ID,
        changes={"title": "Updated", "price_cents": 900},
    )
    client.close()


@pytest.mark.parametrize(
    ("action", "method", "expected_state"),
    [
        ("publish", "publish_item", True),
        ("unpublish", "unpublish_item", False),
    ],
)
def test_admin_publish_and_unpublish(
    action: str,
    method: str,
    expected_state: bool,
) -> None:
    client, service = _client()
    getattr(service, method).return_value = _item(is_published=expected_state)

    response = client.patch(
        f"/api/v1/salons/{SALON_A}/showcase/items/{ITEM_ID}/{action}"
    )

    assert response.status_code == 200
    assert response.json()["is_published"] is expected_state
    getattr(service, method).assert_called_once_with(
        salon_id=SALON_A,
        item_id=ITEM_ID,
    )
    client.close()


def test_admin_delete_item() -> None:
    client, service = _client()

    response = client.delete(f"/api/v1/salons/{SALON_A}/showcase/items/{ITEM_ID}")

    assert response.status_code == 204
    service.delete_item.assert_called_once_with(salon_id=SALON_A, item_id=ITEM_ID)
    client.close()


def test_admin_other_salon_denied_without_membership() -> None:
    client, service = _client()

    response = client.post(
        f"/api/v1/salons/{SALON_B}/showcase/items",
        json={"category": "work", "title": "Attempt", "media_asset_id": str(MEDIA_ID)},
    )

    assert response.status_code == 403
    service.create_item.assert_not_called()
    client.close()


def test_client_cannot_spoof_salon_id_in_body() -> None:
    client, service = _client()

    response = client.post(
        f"/api/v1/salons/{SALON_A}/showcase/items",
        json={
            "salon_id": str(SALON_B),
            "category": "work",
            "title": "Attempt",
            "media_asset_id": str(MEDIA_ID),
        },
    )

    assert response.status_code == 422
    service.create_item.assert_not_called()
    client.close()


def test_admin_cannot_create_item_with_foreign_media() -> None:
    client, service = _client()
    service.create_item.side_effect = ShowcaseMediaNotFoundError("media asset not found")

    response = client.post(
        f"/api/v1/salons/{SALON_A}/showcase/items",
        json={"category": "work", "title": "Attempt", "media_asset_id": str(MEDIA_ID)},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "media asset not found"
    service.create_item.assert_called_once()
    assert service.create_item.call_args.kwargs["salon_id"] == SALON_A
    client.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "other", "title": "Bad", "media_asset_id": str(MEDIA_ID)},
        {"category": "work", "title": "   ", "media_asset_id": str(MEDIA_ID)},
        {"category": "work", "title": "Bad", "media_asset_id": str(MEDIA_ID), "price_cents": -1},
    ],
)
def test_create_validation_rejects_invalid_category_title_and_price(
    payload: dict[str, object],
) -> None:
    client, service = _client()

    response = client.post(f"/api/v1/salons/{SALON_A}/showcase/items", json=payload)

    assert response.status_code == 422
    service.create_item.assert_not_called()
    client.close()


def test_public_showcase_uses_slug_and_category() -> None:
    client, service = _client()
    service.list_public_items_by_slug.return_value = PublicShowcaseItemsResult(
        salon_id=SALON_A,
        salon_slug="salon-a",
        items=(
            PublicShowcaseItem(
                id=ITEM_ID,
                category=ShowcaseCategory.COSMETICS,
                title="Published",
                description=None,
                price_cents=900,
                media_asset_id=MEDIA_ID,
            ),
        ),
    )

    response = client.get(
        "/api/v1/public/salons/salon-a/showcase?category=cosmetics"
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": str(ITEM_ID),
            "category": "cosmetics",
            "title": "Published",
            "description": None,
            "price_cents": 900,
            "image_url": (
                f"/api/v1/public/salons/salon-a/showcase/items/{ITEM_ID}/image"
            ),
        }
    ]
    assert "is_published" not in response.json()["items"][0]
    service.list_public_items_by_slug.assert_called_once_with(
        slug="salon-a",
        category=ShowcaseCategory.COSMETICS,
        limit=50,
        offset=0,
    )
    client.close()


def test_public_image_is_scoped_to_published_showcase_item() -> None:
    from app.services.media.service import MediaService

    client, service = _client()
    service.get_public_image_reference_by_slug.return_value = (
        PublicShowcaseImageReference(salon_id=SALON_A, media_asset_id=MEDIA_ID)
    )
    media_service = MagicMock(spec=MediaService)
    media_service.get_asset.return_value = SimpleNamespace(
        content_type="image/jpeg",
        checksum_sha256=None,
    )
    media_service.open_asset_content.return_value = iter([b"image-bytes"])
    client.app.dependency_overrides[get_media_service] = lambda: media_service

    response = client.get(
        f"/api/v1/public/salons/salon-a/showcase/items/{ITEM_ID}/image"
    )

    assert response.status_code == 200
    assert response.content == b"image-bytes"
    assert response.headers["cache-control"] == "no-store"
    service.get_public_image_reference_by_slug.assert_called_once_with(
        slug="salon-a",
        item_id=ITEM_ID,
    )
    media_service.get_asset.assert_called_once_with(
        salon_id=SALON_A,
        media_id=MEDIA_ID,
    )
    media_service.open_asset_content.assert_called_once_with(
        salon_id=SALON_A,
        media_id=MEDIA_ID,
    )
    client.close()


def test_public_showcase_unknown_salon_is_not_found() -> None:
    from app.services.salon_public.errors import PublicSalonNotFoundError

    client, service = _client()
    service.list_public_items_by_slug.side_effect = PublicSalonNotFoundError(
        "salon not found"
    )

    response = client.get("/api/v1/public/salons/missing/showcase")

    assert response.status_code == 404
    client.close()


def test_admin_write_requires_owner_or_admin_role() -> None:
    client, service = _client(role="staff")

    response = client.post(
        f"/api/v1/salons/{SALON_A}/showcase/items",
        json={"category": "work", "title": "Attempt", "media_asset_id": str(MEDIA_ID)},
    )

    assert response.status_code == 403
    service.create_item.assert_not_called()
    client.close()


def test_admin_route_requires_authentication() -> None:
    client, service = _client()
    del client.headers["Authorization"]

    response = client.get(f"/api/v1/salons/{SALON_A}/showcase/items")

    assert response.status_code == 401
    service.list_items.assert_not_called()
    client.close()


def test_patch_cannot_spoof_salon_id() -> None:
    client, service = _client()

    response = client.patch(
        f"/api/v1/salons/{SALON_A}/showcase/items/{ITEM_ID}",
        json={"salon_id": str(SALON_B), "title": "Spoof"},
    )

    assert response.status_code == 422
    service.update_item.assert_not_called()
    client.close()


@pytest.mark.parametrize(
    ("method", "path", "body", "service_method"),
    [
        (
            "patch",
            f"/api/v1/salons/{SALON_A}/showcase/items/{ITEM_ID}",
            {"title": "Attempt", "is_published": True},
            "update_item",
        ),
        (
            "post",
            f"/api/v1/salons/{SALON_A}/showcase/items",
            {
                "category": "work",
                "title": "Attempt",
                "media_asset_id": str(MEDIA_ID),
                "is_published": True,
            },
            "create_item",
        ),
    ],
)
def test_client_cannot_set_is_published_in_request_body(
    method: str,
    path: str,
    body: dict[str, object],
    service_method: str,
) -> None:
    client, service = _client()

    response = getattr(client, method)(path, json=body)

    assert response.status_code == 422
    getattr(service, service_method).assert_not_called()
    client.close()


@pytest.mark.parametrize(
    ("method", "suffix", "service_method"),
    [
        ("patch", "", "update_item"),
        ("patch", "/publish", "publish_item"),
        ("patch", "/unpublish", "unpublish_item"),
        ("delete", "", "delete_item"),
    ],
)
def test_admin_mutations_of_foreign_item_return_not_found(
    method: str,
    suffix: str,
    service_method: str,
) -> None:
    client, service = _client()
    getattr(service, service_method).side_effect = ShowcaseItemNotFoundError(
        "showcase item not found"
    )
    path = f"/api/v1/salons/{SALON_A}/showcase/items/{ITEM_ID}{suffix}"
    kwargs = {"json": {"title": "Attempt"}} if service_method == "update_item" else {}

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 404
    assert response.json()["detail"] == "showcase item not found"
    getattr(service, service_method).assert_called_once_with(
        salon_id=SALON_A,
        item_id=ITEM_ID,
        **({"changes": {"title": "Attempt"}} if service_method == "update_item" else {}),
    )
    client.close()
