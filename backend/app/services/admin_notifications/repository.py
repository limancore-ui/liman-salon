from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, desc, func, or_, select, update
from sqlalchemy.orm import Session

from app.db.models.admin_notification_event import AdminNotificationEvent
from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.salon_user import SalonUser
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.services.admin_notifications.constants import EVENT_TYPE_PUBLIC_BOOKING_PENDING
from app.services.admin_notifications.types import AdminNotificationRow


class AdminNotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_owner_admin_user_ids(self, salon_id: uuid.UUID) -> list[uuid.UUID]:
        rows = self._session.scalars(
            select(SalonUser.user_id).where(
                SalonUser.salon_id == salon_id,
                SalonUser.is_active.is_(True),
                SalonUser.role.in_(("owner", "admin")),
            )
        ).all()
        return list(rows)

    def add_event(
        self,
        *,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        event_type: str,
    ) -> AdminNotificationEvent:
        event = AdminNotificationEvent(
            salon_id=salon_id,
            booking_id=booking_id,
            recipient_user_id=recipient_user_id,
            event_type=event_type,
        )
        self._session.add(event)
        return event

    def _active_public_pending_query(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> Select[tuple[AdminNotificationEvent, Booking, Customer, Service, Staff]]:
        return (
            select(AdminNotificationEvent, Booking, Customer, Service, Staff)
            .join(
                Booking,
                and_(
                    Booking.salon_id == AdminNotificationEvent.salon_id,
                    Booking.id == AdminNotificationEvent.booking_id,
                ),
            )
            .join(
                Customer,
                and_(
                    Customer.salon_id == Booking.salon_id,
                    Customer.id == Booking.customer_id,
                ),
            )
            .join(
                Service,
                and_(
                    Service.salon_id == Booking.salon_id,
                    Service.id == Booking.service_id,
                ),
            )
            .join(
                Staff,
                and_(
                    Staff.salon_id == Booking.salon_id,
                    Staff.id == Booking.staff_id,
                ),
            )
            .where(
                AdminNotificationEvent.salon_id == salon_id,
                AdminNotificationEvent.recipient_user_id == recipient_user_id,
                Booking.source == "public",
                Booking.status == "pending",
            )
        )

    def list_for_recipient(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[AdminNotificationRow]:
        stmt = (
            self._active_public_pending_query(
                salon_id=salon_id,
                recipient_user_id=recipient_user_id,
            )
            .order_by(desc(AdminNotificationEvent.created_at))
            .limit(limit)
            .offset(offset)
        )
        return [self._row_from_tuple(row) for row in self._session.execute(stmt).all()]

    def count_unread_for_recipient(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(AdminNotificationEvent)
            .join(
                Booking,
                and_(
                    Booking.salon_id == AdminNotificationEvent.salon_id,
                    Booking.id == AdminNotificationEvent.booking_id,
                ),
            )
            .where(
                AdminNotificationEvent.salon_id == salon_id,
                AdminNotificationEvent.recipient_user_id == recipient_user_id,
                AdminNotificationEvent.read_at.is_(None),
                Booking.source == "public",
                Booking.status == "pending",
            )
        )
        return int(self._session.scalar(stmt) or 0)

    def list_since_id(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        after_id: uuid.UUID | None,
        limit: int = 20,
    ) -> list[AdminNotificationRow]:
        stmt = self._active_public_pending_query(
            salon_id=salon_id,
            recipient_user_id=recipient_user_id,
        )
        if after_id is not None:
            anchor = self._session.execute(
                select(
                    AdminNotificationEvent.created_at,
                    AdminNotificationEvent.id,
                ).where(
                    AdminNotificationEvent.id == after_id,
                    AdminNotificationEvent.salon_id == salon_id,
                    AdminNotificationEvent.recipient_user_id == recipient_user_id,
                )
            ).one_or_none()
            if anchor is not None:
                anchor_created_at, anchor_id = anchor
                stmt = stmt.where(
                    or_(
                        AdminNotificationEvent.created_at > anchor_created_at,
                        and_(
                            AdminNotificationEvent.created_at == anchor_created_at,
                            AdminNotificationEvent.id > anchor_id,
                        ),
                    )
                )
        stmt = stmt.order_by(
            AdminNotificationEvent.created_at.asc(),
            AdminNotificationEvent.id.asc(),
        ).limit(limit)
        return [self._row_from_tuple(row) for row in self._session.execute(stmt).all()]

    def mark_read(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        event_id: uuid.UUID,
        read_at: datetime,
    ) -> bool:
        result = self._session.execute(
            update(AdminNotificationEvent)
            .where(
                AdminNotificationEvent.id == event_id,
                AdminNotificationEvent.salon_id == salon_id,
                AdminNotificationEvent.recipient_user_id == recipient_user_id,
                AdminNotificationEvent.read_at.is_(None),
            )
            .values(read_at=read_at)
        )
        return result.rowcount > 0

    def mark_all_read(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        read_at: datetime,
    ) -> int:
        subq = (
            select(AdminNotificationEvent.id)
            .join(
                Booking,
                and_(
                    Booking.salon_id == AdminNotificationEvent.salon_id,
                    Booking.id == AdminNotificationEvent.booking_id,
                ),
            )
            .where(
                AdminNotificationEvent.salon_id == salon_id,
                AdminNotificationEvent.recipient_user_id == recipient_user_id,
                AdminNotificationEvent.read_at.is_(None),
                Booking.source == "public",
                Booking.status == "pending",
            )
        )
        result = self._session.execute(
            update(AdminNotificationEvent)
            .where(AdminNotificationEvent.id.in_(subq))
            .values(read_at=read_at)
        )
        return int(result.rowcount or 0)

    @staticmethod
    def _row_from_tuple(
        row: tuple[AdminNotificationEvent, Booking, Customer, Service, Staff],
    ) -> AdminNotificationRow:
        event, booking, customer, service, staff = row
        return AdminNotificationRow(
            id=event.id,
            event_type=event.event_type,
            booking_id=event.booking_id,
            created_at=event.created_at,
            read_at=event.read_at,
            booking_starts_at=booking.starts_at,
            customer_name=customer.full_name,
            service_name=service.name,
            staff_name=staff.display_name,
        )
