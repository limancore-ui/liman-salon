"""customers table

Revision ID: 20250924_0007
Revises: 20250924_0006
Create Date: 2025-09-24

Salon-scoped customer profiles (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0007"
down_revision: str | None = "20250924_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "bonus_balance_cents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "marketing_opt_in",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "whatsapp_opt_in",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("whatsapp_opt_in_at", sa.DateTime(timezone=True), nullable=True),
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
            "bonus_balance_cents >= 0",
            name="ck_customers_bonus_balance_cents",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_customers_salon_id_id"),
    )
    op.create_index(
        "ix_customers_salon_id_full_name",
        "customers",
        ["salon_id", "full_name"],
        unique=False,
    )
    op.create_index(
        "ix_customers_salon_id_phone",
        "customers",
        ["salon_id", "phone"],
        unique=False,
    )
    op.create_index(
        "ix_customers_user_id",
        "customers",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_customers_salon_id_email_lower",
        "customers",
        ["salon_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_customers_salon_id_email_lower", table_name="customers")
    op.drop_index("ix_customers_user_id", table_name="customers")
    op.drop_index("ix_customers_salon_id_phone", table_name="customers")
    op.drop_index("ix_customers_salon_id_full_name", table_name="customers")
    op.drop_table("customers")
