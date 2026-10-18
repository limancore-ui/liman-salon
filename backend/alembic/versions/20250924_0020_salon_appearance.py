"""salon appearance JSONB + unique salon cover media

Revision ID: 20250924_0020
Revises: 20250924_0019
Create Date: 2025-09-24

Per-salon public branding colors (separate from business settings JSONB).
Canonical one cover attachment per salon for public background image.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20250924_0020"
down_revision: str | None = "20250924_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "salons",
        sa.Column(
            "appearance",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_media_attachments_salon_cover",
        "media_attachments",
        ["salon_id"],
        unique=True,
        postgresql_where=sa.text(
            "entity_type = 'salon' AND purpose = 'cover'"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_media_attachments_salon_cover",
        table_name="media_attachments",
        postgresql_where=sa.text(
            "entity_type = 'salon' AND purpose = 'cover'"
        ),
    )
    op.drop_column("salons", "appearance")
