from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models.salon import Salon


class SalonProfileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_salon(self, salon_id: uuid.UUID) -> Salon | None:
        return self._session.scalar(select(Salon).where(Salon.id == salon_id))

    def update_name(self, salon_id: uuid.UUID, name: str) -> bool:
        result = self._session.execute(
            update(Salon).where(Salon.id == salon_id).values(name=name)
        )
        return result.rowcount > 0
