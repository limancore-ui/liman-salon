"""media_assets and media_attachments tables

Revision ID: 20250924_0016
Revises: 20250924_0015
Create Date: 2025-09-24

Tenant-scoped media metadata and entity attachments (MVP v0.1 Media v1-A).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0016"
down_revision: str | None = "20250924_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEDIA_ENTITY_TYPE_CHECK = "entity_type IN ('salon', 'service', 'staff')"
_MEDIA_PURPOSE_CHECK = "purpose IN ('logo', 'cover', 'avatar', 'gallery')"
_MEDIA_SALON_ENTITY_CHECK = "(entity_type != 'salon') OR (entity_id = salon_id)"


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=127), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("byte_size > 0", name="ck_media_assets_byte_size"),
        sa.CheckConstraint(
            "char_length(storage_key) >= 1",
            name="ck_media_assets_storage_key_min_length",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_media_assets_salon_id_id"),
        sa.UniqueConstraint(
            "salon_id",
            "storage_key",
            name="uq_media_assets_salon_id_storage_key",
        ),
    )
    op.create_index(
        "ix_media_assets_salon_id_created_at",
        "media_assets",
        ["salon_id", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_media_assets_salon_id_not_deleted",
        "media_assets",
        ["salon_id", sa.text("created_at DESC")],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "media_attachments",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_MEDIA_ENTITY_TYPE_CHECK, name="ck_media_attachments_entity_type"),
        sa.CheckConstraint(_MEDIA_PURPOSE_CHECK, name="ck_media_attachments_purpose"),
        sa.CheckConstraint(_MEDIA_SALON_ENTITY_CHECK, name="ck_media_attachments_salon_entity"),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salon_id", "media_asset_id"],
            ["media_assets.salon_id", "media_assets.id"],
            ondelete="CASCADE",
            name="fk_media_attachments_asset_salon_id_media_asset_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_media_attachments_salon_id_entity",
        "media_attachments",
        ["salon_id", "entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "uq_media_attachments_salon_logo",
        "media_attachments",
        ["salon_id"],
        unique=True,
        postgresql_where=sa.text("entity_type = 'salon' AND purpose = 'logo'"),
    )
    op.create_index(
        "uq_media_attachments_service_cover",
        "media_attachments",
        ["salon_id", "entity_id"],
        unique=True,
        postgresql_where=sa.text("entity_type = 'service' AND purpose = 'cover'"),
    )
    op.create_index(
        "uq_media_attachments_staff_avatar",
        "media_attachments",
        ["salon_id", "entity_id"],
        unique=True,
        postgresql_where=sa.text("entity_type = 'staff' AND purpose = 'avatar'"),
    )


def downgrade() -> None:
    op.drop_index("uq_media_attachments_staff_avatar", table_name="media_attachments")
    op.drop_index("uq_media_attachments_service_cover", table_name="media_attachments")
    op.drop_index("uq_media_attachments_salon_logo", table_name="media_attachments")
    op.drop_index("ix_media_attachments_salon_id_entity", table_name="media_attachments")
    op.drop_table("media_attachments")
    op.drop_index("ix_media_assets_salon_id_not_deleted", table_name="media_assets")
    op.drop_index("ix_media_assets_salon_id_created_at", table_name="media_assets")
    op.drop_table("media_assets")
