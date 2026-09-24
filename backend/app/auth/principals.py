from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    id: uuid.UUID
    email: str
    full_name: str


@dataclass(frozen=True, slots=True)
class SalonContext:
    user_id: uuid.UUID
    salon_id: uuid.UUID
    role: str
    salon_name: str
    salon_slug: str
