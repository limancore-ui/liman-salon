"""working_hours table

Revision ID: 20250924_0005
Revises: 20250924_0004
Create Date: 2025-09-24

Recurring weekly salon and staff availability (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0005"
down_revision: str | None = "20250924_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "working_hours",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("staff_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
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
            name="fk_working_hours_staff_salon_id_staff_id",
        ),
        sa.CheckConstraint(
            "day_of_week BETWEEN 0 AND 6",
            name="ck_working_hours_day_of_week",
        ),
        sa.CheckConstraint(
            "start_time < end_time",
            name="ck_working_hours_start_before_end",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_from <= effective_to",
            name="ck_working_hours_effective_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_working_hours_salon_id_staff_id_day_of_week",
        "working_hours",
        ["salon_id", "staff_id", "day_of_week"],
        unique=False,
    )
    op.create_index(
        "ix_working_hours_salon_id_day_of_week",
        "working_hours",
        ["salon_id", "day_of_week"],
        unique=False,
        postgresql_where=sa.text("staff_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_working_hours_salon_id_day_of_week",
        table_name="working_hours",
        postgresql_where=sa.text("staff_id IS NULL"),
    )
    op.drop_index(
        "ix_working_hours_salon_id_staff_id_day_of_week",
        table_name="working_hours",
    )
    op.drop_table("working_hours")
