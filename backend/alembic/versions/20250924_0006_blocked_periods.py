"""blocked_periods table

Revision ID: 20250924_0006
Revises: 20250924_0005
Create Date: 2025-09-24

Salon-wide and staff-specific schedule blocks (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0006"
down_revision: str | None = "20250924_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blocked_periods",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("staff_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "block_type",
            sa.String(length=32),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="CASCADE",
            name="fk_blocked_periods_staff_salon_id_staff_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "starts_at < ends_at",
            name="ck_blocked_periods_starts_before_ends",
        ),
        sa.CheckConstraint(
            "block_type IN ('manual', 'holiday', 'time_off')",
            name="ck_blocked_periods_block_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_blocked_periods_salon_id_staff_id_starts_at_ends_at",
        "blocked_periods",
        ["salon_id", "staff_id", "starts_at", "ends_at"],
        unique=False,
    )
    op.create_index(
        "ix_blocked_periods_salon_id_starts_at",
        "blocked_periods",
        ["salon_id", "starts_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_blocked_periods_salon_id_starts_at",
        table_name="blocked_periods",
    )
    op.drop_index(
        "ix_blocked_periods_salon_id_staff_id_starts_at_ends_at",
        table_name="blocked_periods",
    )
    op.drop_table("blocked_periods")
