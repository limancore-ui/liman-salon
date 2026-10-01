"""Tenant-scoped notification outbox persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.notification import Notification
from app.services.notifications.constants import (
    TEMPLATE_BOOKING_CONFIRMED,
    TEMPLATE_BOOKING_REMINDER_2H,
)


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, notification: Notification) -> None:
        self._session.add(notification)

    def get_confirm_notification(
        self,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> Notification | None:
        return self._session.scalar(
            select(Notification).where(
                Notification.salon_id == salon_id,
                Notification.booking_id == booking_id,
                Notification.template_key == TEMPLATE_BOOKING_CONFIRMED,
            )
        )

    def get_reminder_notification(
        self,
        salon_id: uuid.UUID,
        booking_id: uuid.UUID,
    ) -> Notification | None:
        return self._session.scalar(
            select(Notification).where(
                Notification.salon_id == salon_id,
                Notification.booking_id == booking_id,
                Notification.template_key == TEMPLATE_BOOKING_REMINDER_2H,
            )
        )

    def list_due_pending_for_update(
        self,
        *,
        as_of: datetime,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(
                Notification.status == "pending",
                or_(
                    Notification.scheduled_for.is_(None),
                    Notification.scheduled_for <= as_of,
                ),
            )
            .order_by(Notification.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(self._session.scalars(stmt))
