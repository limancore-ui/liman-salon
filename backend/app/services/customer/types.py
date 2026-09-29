from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CustomerResolveResult:
    customer_id: uuid.UUID
    created: bool


@dataclass(frozen=True, slots=True)
class PublicCustomerLookupResult:
    found: bool
    full_name: str | None
