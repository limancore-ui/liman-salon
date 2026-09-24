"""services table

Revision ID: 20250924_0003
Revises: 20250924_0002
Create Date: 2025-09-24

Creates tenant-scoped service catalog (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0003"
down_revision: str | None = "20250924_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("buffer_before_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("buffer_after_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("duration_minutes > 0", name="ck_services_duration_minutes"),
        sa.CheckConstraint(
            "buffer_before_minutes >= 0 AND buffer_after_minutes >= 0",
            name="ck_services_buffer_minutes",
        ),
        sa.CheckConstraint("price_cents >= 0", name="ck_services_price_cents"),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_services_salon_id_id"),
    )
    op.create_index(
        "ix_services_salon_id_is_active_sort_order",
        "services",
        ["salon_id", "is_active", "sort_order"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_services_salon_id_is_active_sort_order", table_name="services")
    op.drop_table("services")
