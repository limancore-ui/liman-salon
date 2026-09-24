from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.models.staff_service import StaffService


class BookingRepository:
    """Tenant-scoped reads and writes for booking creation."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_salon_currency(self, salon_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(Salon.currency_code).where(Salon.id == salon_id)
        )

    def get_customer(self, salon_id: uuid.UUID, customer_id: uuid.UUID) -> Customer | None:
        return self._session.scalar(
            select(Customer).where(
                Customer.salon_id == salon_id,
                Customer.id == customer_id,
            )
        )

    def get_staff(self, salon_id: uuid.UUID, staff_id: uuid.UUID) -> Staff | None:
        return self._session.scalar(
            select(Staff).where(
                Staff.salon_id == salon_id,
                Staff.id == staff_id,
            )
        )

    def get_service(self, salon_id: uuid.UUID, service_id: uuid.UUID) -> Service | None:
        return self._session.scalar(
            select(Service).where(
                Service.salon_id == salon_id,
                Service.id == service_id,
            )
        )

    def staff_performs_service(
        self,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        service_id: uuid.UUID,
    ) -> bool:
        found = self._session.scalar(
            select(StaffService.id).where(
                StaffService.salon_id == salon_id,
                StaffService.staff_id == staff_id,
                StaffService.service_id == service_id,
            )
        )
        return found is not None

    def expire_stale_pending_holds(
        self,
        *,
        salon_id: uuid.UUID,
        staff_id: uuid.UUID,
        window_start: datetime,
        window_end: datetime,
        as_of: datetime,
    ) -> int:
        """
        Move pending holds with expires_at <= as_of to expired when they overlap
        the staff occupied window. Uses application time (as_of), not DB now().
        """
        stmt = (
            update(Booking)
            .where(
                Booking.salon_id == salon_id,
                Booking.staff_id == staff_id,
                Booking.status == "pending",
                Booking.expires_at.isnot(None),
                Booking.expires_at <= as_of,
                Booking.starts_at < window_end,
                Booking.ends_at > window_start,
            )
            .values(status="expired")
        )
        result = self._session.execute(stmt)
        return result.rowcount or 0

    def add_booking(self, booking: Booking) -> Booking:
        self._session.add(booking)
        self._session.flush()
        return booking
