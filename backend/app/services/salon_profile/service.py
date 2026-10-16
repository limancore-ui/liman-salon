from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.salon_profile.errors import (
    SalonProfileError,
    SalonProfileNotFoundError,
)
from app.services.salon_profile.repository import SalonProfileRepository

NAME_MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class SalonProfileView:
    salon_id: uuid.UUID
    name: str
    slug: str


def normalize_salon_name(raw: str) -> str:
    cleaned = raw.strip()
    if not cleaned:
        raise SalonProfileError("name must not be empty")
    if len(cleaned) > NAME_MAX_LENGTH:
        raise SalonProfileError(
            f"name must be at most {NAME_MAX_LENGTH} characters"
        )
    return cleaned


class SalonProfileService:
    def __init__(self, session: Session) -> None:
        self._repo = SalonProfileRepository(session)

    def get_profile(self, *, salon_id: uuid.UUID) -> SalonProfileView:
        salon = self._repo.get_salon(salon_id)
        if salon is None:
            raise SalonProfileNotFoundError("salon not found")
        return SalonProfileView(
            salon_id=salon.id,
            name=salon.name,
            slug=salon.slug,
        )

    def update_name(self, *, salon_id: uuid.UUID, name: str) -> SalonProfileView:
        cleaned = normalize_salon_name(name)
        salon = self._repo.get_salon(salon_id)
        if salon is None:
            raise SalonProfileNotFoundError("salon not found")
        if salon.name != cleaned:
            if not self._repo.update_name(salon_id, cleaned):
                raise SalonProfileNotFoundError("salon not found")
            salon.name = cleaned
        return SalonProfileView(
            salon_id=salon.id,
            name=salon.name,
            slug=salon.slug,
        )
