"""reviews table

Revision ID: 20250924_0010
Revises: 20250924_0009
Create Date: 2025-09-24

Post-visit feedback with moderation (MVP v0.1).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20250924_0010"
down_revision: str | None = "20250924_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_STATUS_CHECK = (
    "status IN ('pending', 'published', 'rejected', 'hidden')"
)


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("salon_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("booking_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("customer_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("staff_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("moderated_by_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            "rating BETWEEN 1 AND 5",
            name="ck_reviews_rating",
        ),
        sa.CheckConstraint(
            _REVIEW_STATUS_CHECK,
            name="ck_reviews_status",
        ),
        sa.ForeignKeyConstraint(["salon_id"], ["salons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_reviews_booking_salon_id_booking_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_reviews_customer_salon_id_customer_id",
        ),
        sa.ForeignKeyConstraint(
            ["salon_id", "staff_id"],
            ["staff.salon_id", "staff.id"],
            ondelete="SET NULL",
            name="fk_reviews_staff_salon_id_staff_id",
        ),
        sa.ForeignKeyConstraint(
            ["moderated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reviews_salon_id_status_created_at",
        "reviews",
        ["salon_id", "status", sa.text("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_reviews_salon_id_staff_id_status",
        "reviews",
        ["salon_id", "staff_id", "status"],
        unique=False,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_index(
        "uq_reviews_booking_id",
        "reviews",
        ["booking_id"],
        unique=True,
        postgresql_where=sa.text("booking_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_reviews_booking_id", table_name="reviews")
    op.drop_index("ix_reviews_salon_id_staff_id_status", table_name="reviews")
    op.drop_index("ix_reviews_salon_id_status_created_at", table_name="reviews")
    op.drop_table("reviews")
