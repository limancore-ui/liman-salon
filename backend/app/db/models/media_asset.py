from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.media_attachment import MediaAttachment
    from app.db.models.salon import Salon
    from app.db.models.user import User


class MediaAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tenant-scoped uploaded media metadata (bytes live in storage)."""

    __tablename__ = "media_assets"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    salon: Mapped[Salon] = relationship(back_populates="media_assets")
    created_by_user: Mapped[User | None] = relationship()
    attachments: Mapped[list[MediaAttachment]] = relationship(
        back_populates="media_asset",
        cascade="all, delete-orphan",
        overlaps="salon,media_attachments",
    )

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_media_assets_salon_id_id"),
        UniqueConstraint(
            "salon_id",
            "storage_key",
            name="uq_media_assets_salon_id_storage_key",
        ),
        CheckConstraint("byte_size > 0", name="ck_media_assets_byte_size"),
        CheckConstraint(
            "char_length(storage_key) >= 1",
            name="ck_media_assets_storage_key_min_length",
        ),
        Index("ix_media_assets_salon_id_created_at", "salon_id", "created_at"),
        Index(
            "ix_media_assets_salon_id_not_deleted",
            "salon_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
