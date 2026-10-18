from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ShowcaseItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A salon-owned showcase entry referencing an existing media asset."""

    __tablename__ = "showcase_items"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('work', 'cosmetics', 'dyes', 'varnishes')",
            name="ck_showcase_items_category",
        ),
        CheckConstraint(
            "char_length(trim(title)) >= 1",
            name="ck_showcase_items_title_nonempty",
        ),
        CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0",
            name="ck_showcase_items_price_cents_nonnegative",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_showcase_items_sort_order_nonnegative",
        ),
        ForeignKeyConstraint(
            ["salon_id", "media_asset_id"],
            ["media_assets.salon_id", "media_assets.id"],
            ondelete="RESTRICT",
            name="fk_showcase_items_media_asset_salon",
        ),
        Index(
            "ix_showcase_items_salon_published_category_order",
            "salon_id",
            "is_published",
            "category",
            "sort_order",
            "id",
        ),
    )
