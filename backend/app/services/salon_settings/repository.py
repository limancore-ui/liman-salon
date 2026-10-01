from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.salon import Salon


class SalonSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_settings(self, salon_id: uuid.UUID) -> dict[str, Any] | None:
        return self._session.scalar(
            select(Salon.settings).where(Salon.id == salon_id)
        )

    def salon_exists(self, salon_id: uuid.UUID) -> bool:
        found = self._session.scalar(select(Salon.id).where(Salon.id == salon_id))
        return found is not None

    def update_settings(self, salon_id: uuid.UUID, settings: dict[str, Any]) -> bool:
        result = self._session.execute(
            update(Salon)
            .where(Salon.id == salon_id)
            .values(settings=settings)
        )
        return result.rowcount > 0
