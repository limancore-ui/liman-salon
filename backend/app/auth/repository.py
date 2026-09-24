from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.db.models.salon import Salon
from app.db.models.salon_user import SalonUser
from app.db.models.user import User


class AuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_email(self, email: str) -> User | None:
        normalized = normalize_email(email)
        return self._session.scalar(
            select(User).where(func.lower(User.email) == normalized)
        )

    def get_active_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.scalar(
            select(User).where(User.id == user_id, User.is_active.is_(True))
        )

    def get_active_salon(self, salon_id: uuid.UUID) -> Salon | None:
        return self._session.scalar(
            select(Salon).where(Salon.id == salon_id, Salon.is_active.is_(True))
        )

    def get_active_membership(
        self, salon_id: uuid.UUID, user_id: uuid.UUID
    ) -> SalonUser | None:
        return self._session.scalar(
            select(SalonUser).where(
                SalonUser.salon_id == salon_id,
                SalonUser.user_id == user_id,
                SalonUser.is_active.is_(True),
            )
        )
