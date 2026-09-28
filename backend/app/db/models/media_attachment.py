from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.media_asset import MediaAsset
    from app.db.models.salon import Salon


class MediaAttachment(Base, UUIDPrimaryKeyMixin):
    """Links a media asset to a salon, service, or staff entity."""

    __tablename__ = "media_attachments"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    media_asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(
        back_populates="media_attachments",
        overlaps="attachments,media_asset",
    )
    media_asset: Mapped[MediaAsset] = relationship(
        back_populates="attachments",
        overlaps="salon,media_attachments",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "media_asset_id"],
            ["media_assets.salon_id", "media_assets.id"],
            ondelete="CASCADE",
            name="fk_media_attachments_asset_salon_id_media_asset_id",
        ),
        CheckConstraint(
            "entity_type IN ('salon', 'service', 'staff')",
            name="ck_media_attachments_entity_type",
        ),
        CheckConstraint(
            "purpose IN ('logo', 'cover', 'avatar', 'gallery')",
            name="ck_media_attachments_purpose",
        ),
        CheckConstraint(
            "(entity_type != 'salon') OR (entity_id = salon_id)",
            name="ck_media_attachments_salon_entity",
        ),
        Index(
            "ix_media_attachments_salon_id_entity",
            "salon_id",
            "entity_type",
            "entity_id",
        ),
        Index(
            "uq_media_attachments_salon_logo",
            "salon_id",
            unique=True,
            postgresql_where=text("entity_type = 'salon' AND purpose = 'logo'"),
        ),
        Index(
            "uq_media_attachments_service_cover",
            "salon_id",
            "entity_id",
            unique=True,
            postgresql_where=text("entity_type = 'service' AND purpose = 'cover'"),
        ),
        Index(
            "uq_media_attachments_staff_avatar",
            "salon_id",
            "entity_id",
            unique=True,
            postgresql_where=text("entity_type = 'staff' AND purpose = 'avatar'"),
        ),
    )
