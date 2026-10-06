from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.admin_notifications.constants import EVENT_TYPE_PUBLIC_BOOKING_PENDING
from app.services.admin_notifications.repository import AdminNotificationRepository
from app.services.admin_notifications.types import AdminNotificationRow
from app.services.booking.repository import BookingRepository


class AdminNotificationValidationError(ValueError):
    pass


class AdminNotificationNotFoundError(LookupError):
    pass


class AdminNotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = AdminNotificationRepository(session)
        self._bookings = BookingRepository(session)

    def enqueue_public_booking_pending(
        self,
        *,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> int:
        """Create one in-app event per active owner/admin (idempotent per recipient)."""
        booking = self._bookings.get_booking(salon_id, booking_id)
        if booking is None:
            return 0
        if booking.source != "public" or booking.status != "pending":
            return 0

        recipients = self._repo.list_owner_admin_user_ids(salon_id)
        created = 0
        for user_id in recipients:
            try:
                with self._session.begin_nested():
                    self._repo.add_event(
                        salon_id=salon_id,
                        booking_id=booking_id,
                        recipient_user_id=user_id,
                        event_type=EVENT_TYPE_PUBLIC_BOOKING_PENDING,
                    )
                    self._session.flush()
                created += 1
            except IntegrityError:
                continue
        return created

    def list_notifications(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AdminNotificationRow]:
        if limit < 1 or limit > 200:
            raise AdminNotificationValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise AdminNotificationValidationError("offset must be >= 0")
        return self._repo.list_for_recipient(
            salon_id=salon_id,
            recipient_user_id=recipient_user_id,
            limit=limit,
            offset=offset,
        )

    def unread_count(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
    ) -> int:
        return self._repo.count_unread_for_recipient(
            salon_id=salon_id,
            recipient_user_id=recipient_user_id,
        )

    def list_since(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        after_id: uuid.UUID | None,
        limit: int = 20,
    ) -> list[AdminNotificationRow]:
        return self._repo.list_since_id(
            salon_id=salon_id,
            recipient_user_id=recipient_user_id,
            after_id=after_id,
            limit=limit,
        )

    def mark_read(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        event_id: uuid.UUID,
        read_at: datetime,
    ) -> None:
        if read_at.tzinfo is None:
            raise AdminNotificationValidationError("read_at must be timezone-aware")
        updated = self._repo.mark_read(
            salon_id=salon_id,
            recipient_user_id=recipient_user_id,
            event_id=event_id,
            read_at=read_at,
        )
        if not updated:
            raise AdminNotificationNotFoundError("notification not found or already read")

    def mark_all_read(
        self,
        *,
        salon_id: uuid.UUID,
        recipient_user_id: uuid.UUID,
        read_at: datetime,
    ) -> int:
        if read_at.tzinfo is None:
            raise AdminNotificationValidationError("read_at must be timezone-aware")
        return self._repo.mark_all_read(
            salon_id=salon_id,
            recipient_user_id=recipient_user_id,
            read_at=read_at,
        )
