from __future__ import annotations

import re
from collections.abc import Callable

_SLUG_MAX_LEN = 80
_SLUG_MIN_LEN = 2
_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_HYPHEN_RUN = re.compile(r"-+")


def normalize_salon_slug(raw: str) -> str:
    """Lowercase URL-safe slug from arbitrary text (min length 2, max 80)."""
    slug = raw.strip().lower().replace("_", "-").replace(" ", "-")
    slug = _INVALID_CHARS.sub("-", slug)
    slug = _HYPHEN_RUN.sub("-", slug).strip("-")
    if len(slug) < _SLUG_MIN_LEN:
        slug = (slug + "salon")[:_SLUG_MAX_LEN]
        slug = slug.strip("-")
    if len(slug) < _SLUG_MIN_LEN:
        slug = "sa"
    return slug[:_SLUG_MAX_LEN]


def dedupe_salon_slug(base: str, exists: Callable[[str], bool]) -> str:
    """Return base or base-N when slug is already taken (N >= 2)."""
    normalized = normalize_salon_slug(base)
    if not exists(normalized):
        return normalized
    for suffix in range(2, 10_000):
        candidate = _with_suffix(normalized, suffix)
        if not exists(candidate):
            return candidate
    raise ValueError("unable to allocate unique salon slug")


def _with_suffix(base: str, suffix: int) -> str:
    tail = f"-{suffix}"
    max_base = _SLUG_MAX_LEN - len(tail)
    trimmed = base[:max_base].rstrip("-")
    if len(trimmed) < _SLUG_MIN_LEN:
        trimmed = trimmed[: _SLUG_MIN_LEN]
    return f"{trimmed}{tail}"
