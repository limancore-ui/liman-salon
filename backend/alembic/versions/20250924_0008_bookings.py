"""bookings table

Revision ID: 20250924_0008
Revises: 20250924_0007
Create Date: 2025-09-24

Appointments with tenant-safe FKs and GiST overlap exclusion (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0008"
down_revision: str | None = "20250924_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BOOKING_STATUS_CHECK = (
    "status IN ('pending', 'confirmed', 'in_progress', 'completed', "
    "'cancelled', 'no_show', 'expired')"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "bookings",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("staff_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("service_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default=sa.text("'admin'"),
            nullable=False,
        ),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.CHAR(length=3), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=255), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "starts_at < ends_at",
            name="ck_bookings_starts_before_ends",
        ),
        sa.CheckConstraint(
            "duration_minutes > 0",
            name="ck_bookings_duration_minutes",
        ),
        sa.CheckConstraint(
            "price_cents >= 0",
            name="ck_bookings_price_cents",
        ),
        sa.CheckConstraint(_BOOKING_STATUS_CHECK, name="ck_bookings_status"),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_bookings_customer_salon_id_customer_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="RESTRICT",
            name="fk_bookings_staff_salon_id_staff_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "service_id"],
            ["services.salon_id", "services.id"],
            ondelete="RESTRICT",
            name="fk_bookings_service_salon_id_service_id",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("salon_id", "id", name="uq_bookings_salon_id_id"),
    )
    op.create_index(
        "ix_bookings_salon_id_staff_id_starts_at",
        "bookings",
        ["salon_id", "staff_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_bookings_salon_id_customer_id_starts_at",
        "bookings",
        ["salon_id", "customer_id", sa.text("starts_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_bookings_salon_id_status_starts_at",
        "bookings",
        ["salon_id", "status", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_bookings_salon_id_status_expires_at",
        "bookings",
        ["salon_id", "status", "expires_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending' AND expires_at IS NOT NULL"),
    )
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT excl_bookings_staff_time_overlap
        EXCLUDE USING gist (
            staff_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status IN ('pending', 'confirmed', 'in_progress'))
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "excl_bookings_staff_time_overlap",
        "bookings",
        type_="exclude",
    )
    op.drop_index(
        "ix_bookings_salon_id_status_expires_at",
        table_name="bookings",
    )
    op.drop_index(
        "ix_bookings_salon_id_status_starts_at",
        table_name="bookings",
    )
    op.drop_index(
        "ix_bookings_salon_id_customer_id_starts_at",
        table_name="bookings",
    )
    op.drop_index(
        "ix_bookings_salon_id_staff_id_starts_at",
        table_name="bookings",
    )
    op.drop_table("bookings")
