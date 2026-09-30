from __future__ import annotations

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.services.availability.intervals import salon_local_date_range_to_utc_bounds
from app.services.booking.repository import BookingRepository
from app.services.booking.types import BookingUpcomingRow
from app.services.dashboard.errors import DashboardValidationError
from app.services.dashboard.types import (
    AdminDashboardSnapshot,
    DashboardStatusCounts,
    DashboardUpcomingBooking,
    DashboardWarning,
)
from app.services.salon_public.repository import SalonPublicRepository
from app.services.staff.repository import StaffRepository

_UPCOMING_LIMIT = 50


class DashboardService:
    """Aggregated operational snapshot for the admin dashboard."""

    def __init__(self, session: Session) -> None:
        self._booking_repo = BookingRepository(session)
        self._staff_repo = StaffRepository(session)
        self._salon_repo = SalonPublicRepository(session)

    def get_admin_snapshot(
        self,
        *,
        salon_id: uuid.UUID,
        as_of: datetime,
    ) -> AdminDashboardSnapshot:
        if as_of.tzinfo is None:
            raise DashboardValidationError("as_of must be timezone-aware")

        tz_name = self._salon_repo.get_salon_timezone(salon_id)
        if not tz_name:
            raise DashboardValidationError("salon timezone not configured")
        tz = ZoneInfo(tz_name)
        salon_date = as_of.astimezone(tz).date()
        range_start, range_end = salon_local_date_range_to_utc_bounds(
            salon_date, salon_date, tz
        )

        today_booking_count = self._booking_repo.count_bookings_starts_in_range(
            salon_id=salon_id,
            range_start=range_start,
            range_end=range_end,
        )
        raw_status = self._booking_repo.status_counts_starts_in_range(
            salon_id=salon_id,
            range_start=range_start,
            range_end=range_end,
        )
        status_counts = DashboardStatusCounts.from_raw(raw_status)
        upcoming_rows = self._booking_repo.list_upcoming_bookings_starts_in_range(
            salon_id=salon_id,
            range_start=range_start,
            range_end=range_end,
            as_of=as_of,
            limit=_UPCOMING_LIMIT,
        )
        upcoming = [_map_upcoming_row(row) for row in upcoming_rows]
        active_staff_count = self._staff_repo.count_active_staff(salon_id=salon_id)
        warnings = self._derive_warnings(
            salon_id=salon_id,
            active_staff_count=active_staff_count,
        )

        return AdminDashboardSnapshot(
            salon_date=salon_date,
            today_booking_count=today_booking_count,
            status_counts=status_counts,
            upcoming_bookings=upcoming,
            active_staff_count=active_staff_count,
            warnings=warnings,
        )

    def _derive_warnings(
        self,
        *,
        salon_id: uuid.UUID,
        active_staff_count: int,
    ) -> list[DashboardWarning]:
        warnings: list[DashboardWarning] = []
        if active_staff_count == 0:
            warnings.append(DashboardWarning(code="no_active_staff"))
            return warnings

        bookable = self._staff_repo.list_staff(
            salon_id=salon_id,
            active_only=True,
            bookable_only=True,
        )
        if not bookable:
            warnings.append(DashboardWarning(code="no_bookable_staff"))

        return warnings


def _map_upcoming_row(row: BookingUpcomingRow) -> DashboardUpcomingBooking:
    return DashboardUpcomingBooking(
        id=row.id,
        status=row.status,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        price_cents=row.price_cents,
        customer_name=row.customer_name,
        customer_phone=row.customer_phone,
        staff_name=row.staff_name,
        service_name=row.service_name,
    )
