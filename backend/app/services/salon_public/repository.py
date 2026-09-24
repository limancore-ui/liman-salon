from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.salon import Salon


class SalonPublicRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_active_salon_by_slug(self, slug: str) -> Salon | None:
        stmt = select(Salon).where(
            Salon.slug == slug,
            Salon.is_active.is_(True),
        )
        return self._session.scalars(stmt).first()

    def slug_exists(self, slug: str) -> bool:
        stmt = select(Salon.id).where(Salon.slug == slug).limit(1)
        return self._session.scalars(stmt).first() is not None
