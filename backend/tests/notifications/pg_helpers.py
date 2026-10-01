"""Shared PostgreSQL helpers for notification integration tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, insert, select, text
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.db.models.customer import Customer
from app.db.models.notification import Notification
from app.db.models.salon import Salon
from app.db.models.service import Service
from app.db.models.staff import Staff
from app.db.session import engine
from app.services.booking.service import BookingService
from app.services.notifications.service import NotificationService

UTC = timezone.utc
AS_OF = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
SLOT_START = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
SLOT_END = datetime(2026, 4, 20, 11, 0, tzinfo=UTC)
EXPIRES = datetime(2026, 4, 11, 12, 0, tzinfo=UTC)


def postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def confirm_idempotency_constraint_present() -> bool:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_notifications_salon_id_booking_id_template_key'
                    """
                )
            ).first()
            return row is not None
    except Exception:
        return False


def seed_salon_with_booking_entities(
    session: Session,
    *,
    phone: str | None = "+77001234567",
    whatsapp_opt_in: bool = True,
) -> tuple[Salon, Staff, Service, Customer]:
    suffix = uuid.uuid4().hex[:8]
    salon = Salon(
        name=f"Notify {suffix}",
        slug=f"notify-{suffix}",
        timezone="UTC",
        currency_code="KZT",
        is_active=True,
    )
    session.add(salon)
    session.flush()

    staff = Staff(
        salon_id=salon.id,
        display_name="Stylist",
        is_active=True,
        is_bookable=True,
        sort_order=1,
    )
    service = Service(
        salon_id=salon.id,
        name="Cut",
        duration_minutes=60,
        buffer_before_minutes=0,
        buffer_after_minutes=0,
        price_cents=1000,
        is_active=True,
        sort_order=1,
    )
    customer = Customer(
        salon_id=salon.id,
        full_name="Guest",
        phone=phone,
        whatsapp_opt_in=whatsapp_opt_in,
    )
    session.add_all([staff, service, customer])
    session.flush()
    return salon, staff, service, customer


def insert_pending_booking(
    session: Session,
    *,
    salon: Salon,
    staff: Staff,
    service: Service,
    customer: Customer,
) -> uuid.UUID:
    booking_id = uuid.uuid4()
    session.execute(
        insert(Booking.__table__).values(
            id=booking_id,
            salon_id=salon.id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            starts_at=SLOT_START,
            ends_at=SLOT_END,
            status="pending",
            source="public",
            price_cents=service.price_cents,
            currency_code=salon.currency_code,
            duration_minutes=service.duration_minutes,
            expires_at=EXPIRES,
        )
    )
    session.flush()
    return booking_id


def booking_service(session: Session) -> BookingService:
    return BookingService(session, notifications=NotificationService(session))


def notification_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Notification)) or 0
