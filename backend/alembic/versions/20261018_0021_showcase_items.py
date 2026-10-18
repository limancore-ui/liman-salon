"""Create tenant-scoped salon showcase items.

Revision ID: 20261018_0021
Revises: 20250924_0020
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0021"
down_revision: str | None = "20250924_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "showcase_items",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "is_published",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "category IN ('work', 'cosmetics', 'dyes', 'varnishes')",
            name="ck_showcase_items_category",
        ),
        sa.CheckConstraint(
            "char_length(trim(title)) >= 1",
            name="ck_showcase_items_title_nonempty",
        ),
        sa.CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0",
            name="ck_showcase_items_price_cents_nonnegative",
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_showcase_items_sort_order_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id"],
            ["salons.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "media_asset_id"],
            ["media_assets.salon_id", "media_assets.id"],
            ondelete="RESTRICT",
            name="fk_showcase_items_media_asset_salon",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_showcase_items_salon_published_category_order",
        "showcase_items",
        ["salon_id", "is_published", "category", "sort_order", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_showcase_items_salon_published_category_order",
        table_name="showcase_items",
    )
    op.drop_table("showcase_items")
