"""Test bootstrap: DB URL before app.db.session imports the engine."""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://localhost:5432/liman_salon_test",
)
