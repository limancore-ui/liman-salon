from __future__ import annotations

import uuid
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.db.models.showcase_item import ShowcaseItem
from app.services.showcase.errors import (
    ShowcaseItemNotFoundError,
    ShowcaseItemValidationError,
    ShowcaseMediaNotFoundError,
)
from app.services.showcase.repository import ShowcaseRepository
from app.services.showcase.types import (
    PublicShowcaseItem,
    PublicShowcaseImageReference,
    PublicShowcaseItemsResult,
    ShowcaseCategory,
)
from app.services.salon_public.service import SalonPublicService

SHOWCASE_TITLE_MAX_LENGTH = 200
MAX_INTEGER_VALUE = 2_147_483_647


def _normalize_category(value: object) -> ShowcaseCategory:
    try:
        return ShowcaseCategory(value)
    except (TypeError, ValueError) as exc:
        raise ShowcaseItemValidationError("unsupported showcase category") from exc


def _normalize_title(value: object) -> str:
    if not isinstance(value, str):
        raise ShowcaseItemValidationError("title must be a string")
    title = value.strip()
    if not title:
        raise ShowcaseItemValidationError("title must not be empty")
    if len(title) > SHOWCASE_TITLE_MAX_LENGTH:
        raise ShowcaseItemValidationError(
            f"title must be at most {SHOWCASE_TITLE_MAX_LENGTH} characters"
        )
    return title


def _validate_price(value: object) -> int | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_INTEGER_VALUE
    ):
        raise ShowcaseItemValidationError(
            "price_cents must be a non-negative 32-bit integer or None"
        )
    return value


def _validate_sort_order(value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_INTEGER_VALUE
    ):
        raise ShowcaseItemValidationError(
            "sort_order must be a non-negative 32-bit integer"
        )
    return value


class ShowcaseService:
    def __init__(self, session: Session) -> None:
        self._repo = ShowcaseRepository(session)
        self._salon_public = SalonPublicService(session)

    def list_items(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ShowcaseItem]:
        return self._repo.list_items(salon_id=salon_id, limit=limit, offset=offset)

    def create_item(
        self,
        *,
        salon_id: uuid.UUID,
        media_asset_id: uuid.UUID,
        category: ShowcaseCategory | str,
        title: str,
        description: str | None = None,
        price_cents: int | None = None,
        sort_order: int = 0,
    ) -> ShowcaseItem:
        normalized_category = _normalize_category(category)
        normalized_title = _normalize_title(title)
        if description is not None and not isinstance(description, str):
            raise ShowcaseItemValidationError("description must be a string or None")
        normalized_price = _validate_price(price_cents)
        normalized_sort_order = _validate_sort_order(sort_order)

        media_asset = self._repo.get_active_media_asset(
            salon_id=salon_id,
            media_asset_id=media_asset_id,
        )
        if media_asset is None:
            raise ShowcaseMediaNotFoundError("media asset not found")

        item = ShowcaseItem(
            salon_id=salon_id,
            media_asset_id=media_asset_id,
            category=normalized_category.value,
            title=normalized_title,
            description=description,
            price_cents=normalized_price,
            sort_order=normalized_sort_order,
            is_published=False,
        )
        return self._repo.add_item(item)

    def update_item(
        self,
        *,
        salon_id: uuid.UUID,
        item_id: uuid.UUID,
        changes: Mapping[str, object],
    ) -> ShowcaseItem:
        if not changes:
            raise ShowcaseItemValidationError("at least one field must be provided")
        allowed_fields = {
            "title",
            "description",
            "category",
            "price_cents",
            "media_asset_id",
            "sort_order",
        }
        unknown_fields = set(changes) - allowed_fields
        if unknown_fields:
            raise ShowcaseItemValidationError("unsupported showcase item field")

        item = self._repo.get_item_by_id(salon_id=salon_id, item_id=item_id)
        if item is None:
            raise ShowcaseItemNotFoundError("showcase item not found")

        normalized: dict[str, object] = {}
        for field, value in changes.items():
            if field == "title":
                normalized[field] = _normalize_title(value)
            elif field == "category":
                normalized[field] = _normalize_category(value).value
            elif field == "description":
                if value is not None and not isinstance(value, str):
                    raise ShowcaseItemValidationError(
                        "description must be a string or None"
                    )
                normalized[field] = value
            elif field == "price_cents":
                normalized[field] = _validate_price(value)
            elif field == "sort_order":
                normalized[field] = _validate_sort_order(value)
            elif field == "media_asset_id":
                if not isinstance(value, uuid.UUID):
                    raise ShowcaseItemValidationError("media_asset_id must be a UUID")
                if self._repo.get_active_media_asset(
                    salon_id=salon_id,
                    media_asset_id=value,
                ) is None:
                    raise ShowcaseMediaNotFoundError("media asset not found")
                normalized[field] = value

        for field, value in normalized.items():
            setattr(item, field, value)
        return self._repo.save_item(item)

    def publish_item(
        self,
        *,
        salon_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> ShowcaseItem:
        item = self._get_item(salon_id=salon_id, item_id=item_id)
        if self._repo.get_active_media_asset(
            salon_id=salon_id,
            media_asset_id=item.media_asset_id,
        ) is None:
            raise ShowcaseMediaNotFoundError("media asset not found")
        item.is_published = True
        return self._repo.save_item(item)

    def unpublish_item(
        self,
        *,
        salon_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> ShowcaseItem:
        item = self._get_item(salon_id=salon_id, item_id=item_id)
        item.is_published = False
        return self._repo.save_item(item)

    def delete_item(self, *, salon_id: uuid.UUID, item_id: uuid.UUID) -> None:
        item = self._get_item(salon_id=salon_id, item_id=item_id)
        self._repo.delete_item(item)

    def list_public_items_by_slug(
        self,
        *,
        slug: str,
        category: ShowcaseCategory | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> PublicShowcaseItemsResult:
        salon = self._salon_public.resolve_public_salon_by_slug(slug)
        rows = self._repo.list_published_items(
            salon_id=salon.salon_id,
            category=category,
            limit=limit,
            offset=offset,
        )
        items = tuple(
            PublicShowcaseItem(
                id=row.id,
                category=ShowcaseCategory(row.category),
                title=row.title,
                description=row.description,
                price_cents=row.price_cents,
                media_asset_id=row.media_asset_id,
            )
            for row in rows
        )
        return PublicShowcaseItemsResult(
            salon_id=salon.salon_id,
            salon_slug=salon.slug,
            items=items,
        )

    def get_public_image_reference_by_slug(
        self,
        *,
        slug: str,
        item_id: uuid.UUID,
    ) -> PublicShowcaseImageReference:
        salon = self._salon_public.resolve_public_salon_by_slug(slug)
        item = self._repo.get_published_item_by_id(
            salon_id=salon.salon_id,
            item_id=item_id,
        )
        if item is None:
            raise ShowcaseItemNotFoundError("showcase item not found")
        return PublicShowcaseImageReference(
            salon_id=salon.salon_id,
            media_asset_id=item.media_asset_id,
        )

    def _get_item(self, *, salon_id: uuid.UUID, item_id: uuid.UUID) -> ShowcaseItem:
        item = self._repo.get_item_by_id(salon_id=salon_id, item_id=item_id)
        if item is None:
            raise ShowcaseItemNotFoundError("showcase item not found")
        return item
