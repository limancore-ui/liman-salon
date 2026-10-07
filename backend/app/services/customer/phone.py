"""Single source of truth for Kyrgyz customer phone canonicalization.

Canonical stored form: ``+996`` followed by exactly 9 ASCII digits
(e.g. ``+996555123456``). Accepted inputs (after trimming outer whitespace):

* 9 local digits: ``555123456``
* canonical full value: ``+996555123456``

Everything else (other country codes, separators, letters, wrong length) is rejected.
"""

from __future__ import annotations

import re

from app.services.customer.errors import CustomerValidationError

KG_COUNTRY_PREFIX = "+996"
KG_LOCAL_DIGITS = 9

_LOCAL_RE = re.compile(r"[0-9]{9}")
_CANONICAL_RE = re.compile(r"\+996([0-9]{9})")

PHONE_INVALID_MESSAGE = "phone must be +996 followed by 9 digits"


def normalize_kg_phone(value: str) -> str:
    """Return canonical ``+996XXXXXXXXX`` or raise ``CustomerValidationError``."""
    candidate = value.strip()
    if _LOCAL_RE.fullmatch(candidate):
        return f"{KG_COUNTRY_PREFIX}{candidate}"
    if _CANONICAL_RE.fullmatch(candidate):
        return candidate
    raise CustomerValidationError(PHONE_INVALID_MESSAGE)
