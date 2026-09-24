from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import nulls_first, select
from sqlalchemy.orm import Session

from app.db.models.blocked_period import BlockedPeriod
from app.db.models.working_hour import WorkingHour


class ScheduleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_working_hours(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID | None = None,
    ) -> list[WorkingHour]:
        stmt = select(WorkingHour).where(WorkingHour.salon_id == salon_id)
        if staff_id is not None:
            stmt = stmt.where(WorkingHour.staff_id == staff_id)
        stmt = stmt.order_by(
            nulls_first(WorkingHour.staff_id.asc()),
            WorkingHour.staff_id.asc(),
            WorkingHour.day_of_week.asc(),
            WorkingHour.start_time.asc(),
            WorkingHour.id.asc(),
        )
        return list(self._session.scalars(stmt).all())

    def get_working_hour_by_id(
        self, *, salon_id: uuid.UUID, working_hours_id: uuid.UUID
    ) -> WorkingHour | None:
        return self._session.scalar(
            select(WorkingHour).where(
                WorkingHour.salon_id == salon_id,
                WorkingHour.id == working_hours_id,
            )
        )

    def add_working_hour(self, row: WorkingHour) -> WorkingHour:
        self._session.add(row)
        self._session.flush()
        return row

    def delete_working_hour(self, row: WorkingHour) -> None:
        self._session.delete(row)
        self._session.flush()

    def list_blocked_periods(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID | None = None,
        starts_from: datetime | None = None,
        ends_to: datetime | None = None,
        block_type: str | None = None,
    ) -> list[BlockedPeriod]:
        stmt = select(BlockedPeriod).where(BlockedPeriod.salon_id == salon_id)
        if staff_id is not None:
            stmt = stmt.where(BlockedPeriod.staff_id == staff_id)
        if starts_from is not None:
            stmt = stmt.where(BlockedPeriod.ends_at > starts_from)
        if ends_to is not None:
            stmt = stmt.where(BlockedPeriod.starts_at < ends_to)
        if block_type is not None:
            stmt = stmt.where(BlockedPeriod.block_type == block_type)
        stmt = stmt.order_by(
            BlockedPeriod.starts_at.asc(),
            BlockedPeriod.ends_at.asc(),
            BlockedPeriod.id.asc(),
        )
        return list(self._session.scalars(stmt).all())

    def get_blocked_period_by_id(
        self, *, salon_id: uuid.UUID, blocked_period_id: uuid.UUID
    ) -> BlockedPeriod | None:
        return self._session.scalar(
            select(BlockedPeriod).where(
                BlockedPeriod.salon_id == salon_id,
                BlockedPeriod.id == blocked_period_id,
            )
        )

    def add_blocked_period(self, row: BlockedPeriod) -> BlockedPeriod:
        self._session.add(row)
        self._session.flush()
        return row

    def delete_blocked_period(self, row: BlockedPeriod) -> None:
        self._session.delete(row)
        self._session.flush()

    def flush(self) -> None:
        self._session.flush()
