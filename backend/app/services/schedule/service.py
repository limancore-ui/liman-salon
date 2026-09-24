from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone

from sqlalchemy.orm import Session

from app.db.models.blocked_period import BlockedPeriod
from app.db.models.working_hour import WorkingHour
from app.services.schedule.errors import ScheduleNotFoundError, ScheduleValidationError
from app.services.schedule.repository import ScheduleRepository
from app.services.staff.repository import StaffRepository

_BLOCK_TYPES = frozenset({"manual", "holiday", "time_off"})


@dataclass(frozen=True, slots=True)
class WorkingHoursCreateData:
    staff_id: uuid.UUID | None
    day_of_week: int
    start_time: time
    end_time: time
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class WorkingHoursUpdateData:
    staff_id: uuid.UUID | None = None
    day_of_week: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    set_staff_id: bool = False
    set_effective_from: bool = False
    set_effective_to: bool = False


@dataclass(frozen=True, slots=True)
class BlockedPeriodCreateData:
    staff_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    reason: str | None = None
    block_type: str = "manual"


@dataclass(frozen=True, slots=True)
class BlockedPeriodUpdateData:
    staff_id: uuid.UUID | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    reason: str | None = None
    block_type: str | None = None
    set_staff_id: bool = False
    set_reason: bool = False


class ScheduleService:
    def __init__(self, session: Session) -> None:
        self._repo = ScheduleRepository(session)
        self._staff_repo = StaffRepository(session)

    def list_working_hours(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID | None = None,
    ) -> list[WorkingHour]:
        return self._repo.list_working_hours(salon_id=salon_id, staff_id=staff_id)

    def get_working_hour(
        self, *, salon_id: uuid.UUID, working_hours_id: uuid.UUID
    ) -> WorkingHour:
        row = self._repo.get_working_hour_by_id(
            salon_id=salon_id, working_hours_id=working_hours_id
        )
        if row is None:
            raise ScheduleNotFoundError("working hours not found")
        return row

    def create_working_hour(
        self, *, salon_id: uuid.UUID, data: WorkingHoursCreateData
    ) -> WorkingHour:
        if data.staff_id is not None:
            self._ensure_staff_in_salon(salon_id=salon_id, staff_id=data.staff_id)
        self._validate_working_hour(
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        row = WorkingHour(
            salon_id=salon_id,
            staff_id=data.staff_id,
            day_of_week=data.day_of_week,
            start_time=data.start_time,
            end_time=data.end_time,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        created = self._repo.add_working_hour(row)
        return self.get_working_hour(salon_id=salon_id, working_hours_id=created.id)

    def update_working_hour(
        self,
        *,
        salon_id: uuid.UUID,
        working_hours_id: uuid.UUID,
        data: WorkingHoursUpdateData,
    ) -> WorkingHour:
        row = self.get_working_hour(salon_id=salon_id, working_hours_id=working_hours_id)
        if data.set_staff_id:
            if data.staff_id is not None:
                self._ensure_staff_in_salon(salon_id=salon_id, staff_id=data.staff_id)
            row.staff_id = data.staff_id
        if data.day_of_week is not None:
            row.day_of_week = data.day_of_week
        if data.start_time is not None:
            row.start_time = data.start_time
        if data.end_time is not None:
            row.end_time = data.end_time
        if data.set_effective_from:
            row.effective_from = data.effective_from
        if data.set_effective_to:
            row.effective_to = data.effective_to
        self._validate_working_hour(
            day_of_week=row.day_of_week,
            start_time=row.start_time,
            end_time=row.end_time,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        )
        self._repo.flush()
        return row

    def delete_working_hour(
        self, *, salon_id: uuid.UUID, working_hours_id: uuid.UUID
    ) -> None:
        row = self.get_working_hour(salon_id=salon_id, working_hours_id=working_hours_id)
        self._repo.delete_working_hour(row)

    def list_blocked_periods(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID | None = None,
        starts_from: datetime | None = None,
        ends_to: datetime | None = None,
        block_type: str | None = None,
    ) -> list[BlockedPeriod]:
        if starts_from is not None:
            starts_from = self._normalize_instant(starts_from)
        if ends_to is not None:
            ends_to = self._normalize_instant(ends_to)
        if block_type is not None and block_type not in _BLOCK_TYPES:
            raise ScheduleValidationError("invalid block_type")
        return self._repo.list_blocked_periods(
            salon_id=salon_id,
            staff_id=staff_id,
            starts_from=starts_from,
            ends_to=ends_to,
            block_type=block_type,
        )

    def get_blocked_period(
        self, *, salon_id: uuid.UUID, blocked_period_id: uuid.UUID
    ) -> BlockedPeriod:
        row = self._repo.get_blocked_period_by_id(
            salon_id=salon_id, blocked_period_id=blocked_period_id
        )
        if row is None:
            raise ScheduleNotFoundError("blocked period not found")
        return row

    def create_blocked_period(
        self,
        *,
        salon_id: uuid.UUID,
        created_by_user_id: uuid.UUID,
        data: BlockedPeriodCreateData,
    ) -> BlockedPeriod:
        if data.staff_id is not None:
            self._ensure_staff_in_salon(salon_id=salon_id, staff_id=data.staff_id)
        starts_at = self._normalize_instant(data.starts_at)
        ends_at = self._normalize_instant(data.ends_at)
        self._validate_blocked_period(
            starts_at=starts_at,
            ends_at=ends_at,
            block_type=data.block_type,
        )
        row = BlockedPeriod(
            salon_id=salon_id,
            staff_id=data.staff_id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=data.reason,
            block_type=data.block_type,
            created_by_user_id=created_by_user_id,
        )
        created = self._repo.add_blocked_period(row)
        return self.get_blocked_period(salon_id=salon_id, blocked_period_id=created.id)

    def update_blocked_period(
        self,
        *,
        salon_id: uuid.UUID,
        blocked_period_id: uuid.UUID,
        data: BlockedPeriodUpdateData,
    ) -> BlockedPeriod:
        row = self.get_blocked_period(salon_id=salon_id, blocked_period_id=blocked_period_id)
        if data.set_staff_id:
            if data.staff_id is not None:
                self._ensure_staff_in_salon(salon_id=salon_id, staff_id=data.staff_id)
            row.staff_id = data.staff_id
        if data.starts_at is not None:
            row.starts_at = self._normalize_instant(data.starts_at)
        if data.ends_at is not None:
            row.ends_at = self._normalize_instant(data.ends_at)
        if data.set_reason:
            row.reason = data.reason
        if data.block_type is not None:
            row.block_type = data.block_type
        self._validate_blocked_period(
            starts_at=row.starts_at,
            ends_at=row.ends_at,
            block_type=row.block_type,
        )
        self._repo.flush()
        return row

    def delete_blocked_period(
        self, *, salon_id: uuid.UUID, blocked_period_id: uuid.UUID
    ) -> None:
        row = self.get_blocked_period(salon_id=salon_id, blocked_period_id=blocked_period_id)
        self._repo.delete_blocked_period(row)

    def _ensure_staff_in_salon(
        self, *, salon_id: uuid.UUID, staff_id: uuid.UUID
    ) -> None:
        staff = self._staff_repo.get_staff_by_id(salon_id=salon_id, staff_id=staff_id)
        if staff is None:
            raise ScheduleNotFoundError("staff not found")

    @staticmethod
    def _validate_working_hour(
        *,
        day_of_week: int,
        start_time: time,
        end_time: time,
        effective_from: date | None,
        effective_to: date | None,
    ) -> None:
        if day_of_week < 0 or day_of_week > 6:
            raise ScheduleValidationError("day_of_week must be between 0 and 6")
        if start_time >= end_time:
            raise ScheduleValidationError("start_time must be before end_time")
        if effective_from is not None and effective_to is not None:
            if effective_to < effective_from:
                raise ScheduleValidationError(
                    "effective_to must be on or after effective_from"
                )

    @staticmethod
    def _validate_blocked_period(
        *,
        starts_at: datetime,
        ends_at: datetime,
        block_type: str,
    ) -> None:
        if block_type not in _BLOCK_TYPES:
            raise ScheduleValidationError("invalid block_type")
        if starts_at >= ends_at:
            raise ScheduleValidationError("starts_at must be before ends_at")

    @staticmethod
    def _normalize_instant(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ScheduleValidationError("datetime must be timezone-aware")
        return value.astimezone(timezone.utc)
