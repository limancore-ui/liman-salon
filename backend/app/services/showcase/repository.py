from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.media_asset import MediaAsset
from app.db.models.showcase_item import ShowcaseItem
from app.services.showcase.types import ShowcaseCategory


class ShowcaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_media_asset(
        self,
        *,
        salon_id: uuid.UUID,
        media_asset_id: uuid.UUID,
    ) -> MediaAsset | None:
        return self._session.scalar(
            select(MediaAsset).where(
                MediaAsset.salon_id == salon_id,
                MediaAsset.id == media_asset_id,
                MediaAsset.deleted_at.is_(None),
            )
        )

    def list_items(
        self,
        *,
        salon_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[ShowcaseItem]:
        stmt = (
            select(ShowcaseItem)
            .where(ShowcaseItem.salon_id == salon_id)
            .order_by(ShowcaseItem.sort_order.asc(), ShowcaseItem.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt).all())

    def list_published_items(
        self,
        *,
        salon_id: uuid.UUID,
        category: ShowcaseCategory | None,
        limit: int,
        offset: int,
    ) -> list[ShowcaseItem]:
        stmt = (
            select(ShowcaseItem)
            .join(
                MediaAsset,
                (MediaAsset.salon_id == ShowcaseItem.salon_id)
                & (MediaAsset.id == ShowcaseItem.media_asset_id),
            )
            .where(
                ShowcaseItem.salon_id == salon_id,
                ShowcaseItem.is_published.is_(True),
                MediaAsset.deleted_at.is_(None),
            )
        )
        if category is not None:
            stmt = stmt.where(ShowcaseItem.category == category.value)
        stmt = (
            stmt.order_by(ShowcaseItem.sort_order.asc(), ShowcaseItem.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt).all())

    def get_item_by_id(
        self,
        *,
        salon_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> ShowcaseItem | None:
        return self._session.scalar(
            select(ShowcaseItem).where(
                ShowcaseItem.salon_id == salon_id,
                ShowcaseItem.id == item_id,
            )
        )

    def get_published_item_by_id(
        self,
        *,
        salon_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> ShowcaseItem | None:
        return self._session.scalar(
            select(ShowcaseItem)
            .join(
                MediaAsset,
                (MediaAsset.salon_id == ShowcaseItem.salon_id)
                & (MediaAsset.id == ShowcaseItem.media_asset_id),
            )
            .where(
                ShowcaseItem.salon_id == salon_id,
                ShowcaseItem.id == item_id,
                ShowcaseItem.is_published.is_(True),
                MediaAsset.deleted_at.is_(None),
            )
        )

    def add_item(self, item: ShowcaseItem) -> ShowcaseItem:
        self._session.add(item)
        self._session.flush()
        return item

    def save_item(self, item: ShowcaseItem) -> ShowcaseItem:
        self._session.flush()
        return item

    def delete_item(self, item: ShowcaseItem) -> None:
        self._session.delete(item)
        self._session.flush()
