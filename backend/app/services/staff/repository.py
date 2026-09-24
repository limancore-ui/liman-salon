from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.staff import Staff


class StaffRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_staff(
        self,
        *,
        salon_id: uuid.UUID,
        active_only: bool = True,
        bookable_only: bool = False,
    ) -> list[Staff]:
        stmt = select(Staff).where(Staff.salon_id == salon_id)
        if active_only:
            stmt = stmt.where(Staff.is_active.is_(True))
        if bookable_only:
            stmt = stmt.where(Staff.is_bookable.is_(True))
        stmt = stmt.order_by(Staff.sort_order, Staff.display_name, Staff.id)
        return list(self._session.scalars(stmt).all())

    def get_staff_by_id(self, *, salon_id: uuid.UUID, staff_id: uuid.UUID) -> Staff | None:
        return self._session.scalar(
            select(Staff).where(Staff.salon_id == salon_id, Staff.id == staff_id)
        )

    def add_staff(self, staff: Staff) -> Staff:
        self._session.add(staff)
        self._session.flush()
        return staff

    def flush(self) -> None:
        self._session.flush()
