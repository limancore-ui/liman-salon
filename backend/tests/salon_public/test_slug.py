from __future__ import annotations

import pytest
from sqlalchemy import UniqueConstraint

from app.db.models.salon import Salon
from app.services.salon_public.slug import dedupe_salon_slug, normalize_salon_slug


def test_normalize_lowercase_and_hyphens() -> None:
    assert normalize_salon_slug("  Liman Demo! ") == "liman-demo"
    assert normalize_salon_slug("foo__bar") == "foo-bar"


def test_normalize_min_length() -> None:
    assert len(normalize_salon_slug("-")) >= 2
    assert len(normalize_salon_slug("a")) >= 2


def test_dedupe_appends_numeric_suffix() -> None:
    taken = {"liman-demo"}

    def exists(slug: str) -> bool:
        return slug in taken

    assert dedupe_salon_slug("liman-demo", exists) == "liman-demo-2"
    taken.add("liman-demo-2")
    assert dedupe_salon_slug("liman-demo", exists) == "liman-demo-3"


def test_salon_slug_unique_constraint_on_model() -> None:
    uniques = [
        c
        for c in Salon.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]
    slug_unique = any(
        "slug" in c.columns.keys() and len(c.columns) == 1 for c in uniques
    )
    assert slug_unique
