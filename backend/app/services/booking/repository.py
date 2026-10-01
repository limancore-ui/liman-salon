from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, func, select, update
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.services.booking.types import BookingListRow, BookingUpcomingRow
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

    def get_salon_settings(self, salon_id: uuid.UUID) -> dict | None:
        return self._session.scalar(
            select(Salon.settings).where(Salon.id == salon_id)
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

    def expire_all_stale_pending_holds(self, *, as_of: datetime) -> int:
        """
        Global sweeper: move all pending holds with expires_at <= as_of to expired.
        Uses application time (as_of), not DB now(). Not tenant-scoped.
        """
        stmt = (
            update(Booking)
            .where(
                Booking.status == "pending",
                Booking.expires_at.isnot(None),
                Booking.expires_at <= as_of,
            )
            .values(status="expired", updated_at=as_of)
        )
        result = self._session.execute(stmt)
        return result.rowcount or 0

    def get_booking(
        self,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> Booking | None:
        return self._session.scalar(
            select(Booking).where(
                Booking.salon_id == salon_id,
                Booking.id == booking_id,
            )
        )

    def add_booking(self, booking: Booking) -> Booking:
        self._session.add(booking)
        self._session.flush()
        return booking

    def list_bookings(
        self,
        *,
        salon_id: uuid.UUID,
        starts_at_from: datetime | None,
        starts_at_to: datetime | None,
        status: str | None,
        staff_id: uuid.UUID | None,
        limit: int,
        offset: int,
    ) -> list[BookingListRow]:
        stmt = (
            select(
                Booking.id,
                Booking.status,
                Booking.starts_at,
                Booking.ends_at,
                Booking.duration_minutes,
                Booking.price_cents,
                Customer.full_name,
                Customer.phone,
                Staff.display_name,
                Service.name,
                Booking.source,
                Booking.created_at,
            )
            .join(
                Customer,
                and_(
                    Booking.salon_id == Customer.salon_id,
                    Booking.customer_id == Customer.id,
                ),
            )
            .join(
                Staff,
                and_(
                    Booking.salon_id == Staff.salon_id,
                    Booking.staff_id == Staff.id,
                ),
            )
            .join(
                Service,
                and_(
                    Booking.salon_id == Service.salon_id,
                    Booking.service_id == Service.id,
                ),
            )
            .where(Booking.salon_id == salon_id)
        )
        if starts_at_from is not None:
            stmt = stmt.where(Booking.starts_at >= starts_at_from)
        if starts_at_to is not None:
            stmt = stmt.where(Booking.starts_at < starts_at_to)
        if status is not None:
            stmt = stmt.where(Booking.status == status)
        if staff_id is not None:
            stmt = stmt.where(Booking.staff_id == staff_id)
        stmt = (
            stmt.order_by(Booking.starts_at.desc(), Booking.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self._session.execute(stmt).all()
        return [
            BookingListRow(
                id=row.id,
                status=row.status,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                duration_minutes=row.duration_minutes,
                price_cents=row.price_cents,
                customer_name=row.full_name,
                customer_phone=row.phone,
                staff_name=row.display_name,
                service_name=row.name,
                source=row.source,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def count_bookings_starts_in_range(
        self,
        *,
        salon_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Booking)
            .where(
                Booking.salon_id == salon_id,
                Booking.starts_at >= range_start,
                Booking.starts_at < range_end,
            )
        )
        return int(self._session.scalar(stmt) or 0)

    def status_counts_starts_in_range(
        self,
        *,
        salon_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
    ) -> dict[str, int]:
        stmt = (
            select(Booking.status, func.count())
            .where(
                Booking.salon_id == salon_id,
                Booking.starts_at >= range_start,
                Booking.starts_at < range_end,
            )
            .group_by(Booking.status)
        )
        rows = self._session.execute(stmt).all()
        return {status: int(count) for status, count in rows}

    def list_upcoming_bookings_starts_in_range(
        self,
        *,
        salon_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
        as_of: datetime,
        limit: int,
    ) -> list[BookingUpcomingRow]:
        stmt = (
            select(
                Booking.id,
                Booking.status,
                Booking.starts_at,
                Booking.ends_at,
                Booking.price_cents,
                Customer.full_name,
                Customer.phone,
                Staff.display_name,
                Service.name,
            )
            .join(
                Customer,
                and_(
                    Booking.salon_id == Customer.salon_id,
                    Booking.customer_id == Customer.id,
                ),
            )
            .join(
                Staff,
                and_(
                    Booking.salon_id == Staff.salon_id,
                    Booking.staff_id == Staff.id,
                ),
            )
            .join(
                Service,
                and_(
                    Booking.salon_id == Service.salon_id,
                    Booking.service_id == Service.id,
                ),
            )
            .where(
                Booking.salon_id == salon_id,
                Booking.starts_at >= range_start,
                Booking.starts_at < range_end,
                Booking.starts_at >= as_of,
            )
            .order_by(Booking.starts_at.asc(), Booking.id.asc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).all()
        return [
            BookingUpcomingRow(
                id=row.id,
                status=row.status,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                price_cents=row.price_cents,
                customer_name=row.full_name,
                customer_phone=row.phone,
                staff_name=row.display_name,
                service_name=row.name,
            )
            for row in rows
        ]

    _ATTENTION_OPERATIONAL_STATUSES = ("pending", "confirmed", "in_progress")

    def list_attention_bookings_starts_in_range(
        self,
        *,
        salon_id: uuid.UUID,
        range_start: datetime,
        range_end: datetime,
        limit: int,
    ) -> list[BookingUpcomingRow]:
        stmt = (
            select(
                Booking.id,
                Booking.status,
                Booking.starts_at,
                Booking.ends_at,
                Booking.price_cents,
                Customer.full_name,
                Customer.phone,
                Staff.display_name,
                Service.name,
            )
            .join(
                Customer,
                and_(
                    Booking.salon_id == Customer.salon_id,
                    Booking.customer_id == Customer.id,
                ),
            )
            .join(
                Staff,
                and_(
                    Booking.salon_id == Staff.salon_id,
                    Booking.staff_id == Staff.id,
                ),
            )
            .join(
                Service,
                and_(
                    Booking.salon_id == Service.salon_id,
                    Booking.service_id == Service.id,
                ),
            )
            .where(
                Booking.salon_id == salon_id,
                Booking.starts_at >= range_start,
                Booking.starts_at < range_end,
                Booking.status.in_(self._ATTENTION_OPERATIONAL_STATUSES),
            )
            .order_by(Booking.starts_at.asc(), Booking.id.asc())
            .limit(limit)
        )
        rows = self._session.execute(stmt).all()
        return [
            BookingUpcomingRow(
                id=row.id,
                status=row.status,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                price_cents=row.price_cents,
                customer_name=row.full_name,
                customer_phone=row.phone,
                staff_name=row.display_name,
                service_name=row.name,
            )
            for row in rows
        ]
