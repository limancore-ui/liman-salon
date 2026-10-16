from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.salon import Salon


class SalonAppearanceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_appearance(self, salon_id: uuid.UUID) -> dict[str, Any] | None:
        return self._session.scalar(
            select(Salon.appearance).where(Salon.id == salon_id)
        )

    def get_salon_name(self, salon_id: uuid.UUID) -> str | None:
        return self._session.scalar(select(Salon.name).where(Salon.id == salon_id))

    def salon_exists(self, salon_id: uuid.UUID) -> bool:
        found = self._session.scalar(select(Salon.id).where(Salon.id == salon_id))
        return found is not None

    def update_appearance(
        self, salon_id: uuid.UUID, appearance: dict[str, Any]
    ) -> bool:
        result = self._session.execute(
            update(Salon)
            .where(Salon.id == salon_id)
            .values(appearance=appearance)
        )
        return result.rowcount > 0
