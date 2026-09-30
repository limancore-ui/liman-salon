"""bookings.manage_token_hash for public manage links

Revision ID: 20250924_0017
Revises: 20250924_0016
Create Date: 2025-09-24

HMAC-SHA256 hex digest of public booking manage token (set at public create only).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20250924_0017"
down_revision: str | None = "20250924_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("manage_token_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bookings", "manage_token_hash")
