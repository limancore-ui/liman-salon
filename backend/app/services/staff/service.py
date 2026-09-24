from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models.staff import Staff
from app.services.staff.errors import StaffNotFoundError, StaffValidationError
from app.services.staff.repository import StaffRepository

_COLOR_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass(frozen=True, slots=True)
class StaffCreateData:
    display_name: str
    title: str | None = None
    bio: str | None = None
    color_hex: str | None = None
    is_bookable: bool = True
    is_active: bool = True
    sort_order: int = 0


@dataclass(frozen=True, slots=True)
class StaffUpdateData:
    display_name: str | None = None
    title: str | None = None
    bio: str | None = None
    color_hex: str | None = None
    is_bookable: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class StaffService:
    def __init__(self, session: Session) -> None:
        self._repo = StaffRepository(session)

    def list_staff(
        self,
        *,
        salon_id: uuid.UUID,
        active_only: bool = True,
        bookable_only: bool = False,
    ) -> list[Staff]:
        return self._repo.list_staff(
            salon_id=salon_id,
            active_only=active_only,
            bookable_only=bookable_only,
        )

    def get_staff(self, *, salon_id: uuid.UUID, staff_id: uuid.UUID) -> Staff:
        row = self._repo.get_staff_by_id(salon_id=salon_id, staff_id=staff_id)
        if row is None:
            raise StaffNotFoundError("staff not found")
        return row

    def create_staff(self, *, salon_id: uuid.UUID, data: StaffCreateData) -> Staff:
        self._validate_create(data)
        staff = Staff(
            salon_id=salon_id,
            display_name=data.display_name.strip(),
            title=data.title,
            bio=data.bio,
            color_hex=data.color_hex,
            is_bookable=data.is_bookable,
            is_active=data.is_active,
            sort_order=data.sort_order,
        )
        return self._repo.add_staff(staff)

    def update_staff(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        data: StaffUpdateData,
    ) -> Staff:
        staff = self.get_staff(salon_id=salon_id, staff_id=staff_id)
        if data.display_name is not None:
            name = data.display_name.strip()
            if not name:
                raise StaffValidationError("display_name must not be blank")
            staff.display_name = name
        if data.title is not None:
            staff.title = data.title
        if data.bio is not None:
            staff.bio = data.bio
        if data.color_hex is not None:
            self._validate_color_hex(data.color_hex)
            staff.color_hex = data.color_hex
        if data.is_bookable is not None:
            staff.is_bookable = data.is_bookable
        if data.is_active is not None:
            staff.is_active = data.is_active
        if data.sort_order is not None:
            if data.sort_order < 0:
                raise StaffValidationError("sort_order must be >= 0")
            staff.sort_order = data.sort_order
        self._repo.flush()
        return staff

    @staticmethod
    def _validate_create(data: StaffCreateData) -> None:
        if not data.display_name or not data.display_name.strip():
            raise StaffValidationError("display_name must not be blank")
        if data.sort_order < 0:
            raise StaffValidationError("sort_order must be >= 0")
        if data.color_hex is not None:
            StaffService._validate_color_hex(data.color_hex)

    @staticmethod
    def _validate_color_hex(value: str) -> None:
        if not _COLOR_HEX.match(value):
            raise StaffValidationError("color_hex must match #RRGGBB")
