"""staff_services table

Revision ID: 20250924_0004
Revises: 20250924_0003
Create Date: 2025-09-24

Staff–service eligibility junction (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0004"
down_revision: str | None = "20250924_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_services",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("staff_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("service_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="CASCADE",
            name="fk_staff_services_staff_salon_id_staff_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "service_id"],
            ["services.salon_id", "services.id"],
            ondelete="CASCADE",
            name="fk_staff_services_service_salon_id_service_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id", "service_id", name="uq_staff_services_staff_id_service_id"),
        sa.UniqueConstraint(
            "salon_id",
            "staff_id",
            "service_id",
            name="uq_staff_services_salon_id_staff_id_service_id",
        ),
    )
    op.create_index(
        "ix_staff_services_salon_id_service_id",
        "staff_services",
        ["salon_id", "service_id"],
        unique=False,
    )
    op.create_index(
        "ix_staff_services_salon_id_staff_id",
        "staff_services",
        ["salon_id", "staff_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_staff_services_salon_id_staff_id", table_name="staff_services")
    op.drop_index("ix_staff_services_salon_id_service_id", table_name="staff_services")
    op.drop_table("staff_services")
