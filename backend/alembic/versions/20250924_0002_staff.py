"""staff table

Revision ID: 20250924_0002
Revises: 20250924_0001
Create Date: 2025-09-24

Creates tenant-scoped staff profiles (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0002"
down_revision: str | None = "20250924_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("color_hex", sa.CHAR(7), nullable=True),
        sa.Column("is_bookable", sa.Boolean(), server_default="true", nullable=False),
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
        sa.CheckConstraint(
            "color_hex IS NULL OR color_hex ~ '^#[0-9A-Fa-f]{6}$'",
            name="ck_staff_color_hex",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_staff_salon_id_id"),
    )
    op.create_index(
        "ix_staff_salon_id_is_active_is_bookable",
        "staff",
        ["salon_id", "is_active", "is_bookable"],
        unique=False,
    )
    op.create_index(
        "ix_staff_user_id",
        "staff",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_staff_salon_id_user_id",
        "staff",
        ["salon_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_staff_salon_id_user_id", table_name="staff")
    op.drop_index("ix_staff_user_id", table_name="staff")
    op.drop_index("ix_staff_salon_id_is_active_is_bookable", table_name="staff")
    op.drop_table("staff")
