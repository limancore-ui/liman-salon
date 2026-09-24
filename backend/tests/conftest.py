"""Test bootstrap: DB URL before app.db.session imports the engine."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://localhost:5432/liman_salon_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "01234567890123456789012345678901",
)

from app.core.config import get_settings

get_settings.cache_clear()
