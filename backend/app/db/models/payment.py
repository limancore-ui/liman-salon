from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    desc,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.salon import Salon
    from app.db.models.subscription import Subscription

_PAYMENT_STATUS_CHECK = (
    "status IN ('pending', 'processing', 'succeeded', 'failed', "
    "'refunded', 'partially_refunded', 'cancelled')"
)


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Charges linked to subscription billing and/or booking checkout."""

    __tablename__ = "payments"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_code: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="pending",
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="manual",
    )
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    salon: Mapped[Salon] = relationship(back_populates="payments")
    subscription: Mapped[Subscription | None] = relationship(
        back_populates="payments",
        foreign_keys=[salon_id, subscription_id],
    )
    booking: Mapped[Booking | None] = relationship(
        back_populates="payments",
        foreign_keys=[salon_id, booking_id],
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "subscription_id"],
            ["subscriptions.salon_id", "subscriptions.id"],
            ondelete="SET NULL",
            name="fk_payments_subscription_salon_id_subscription_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_payments_booking_salon_id_booking_id",
        ),
        CheckConstraint(
            "amount_cents > 0",
            name="ck_payments_amount_cents",
        ),
        CheckConstraint(_PAYMENT_STATUS_CHECK, name="ck_payments_status"),
        CheckConstraint(
            "(subscription_id IS NOT NULL) OR (booking_id IS NOT NULL)",
            name="ck_payments_business_anchor",
        ),
        Index(
            "ix_payments_salon_id_status_created_at",
            "salon_id",
            "status",
            desc("created_at"),
        ),
        Index(
            "ix_payments_salon_id_subscription_id",
            "salon_id",
            "subscription_id",
            postgresql_where=text("subscription_id IS NOT NULL"),
        ),
        Index(
            "ix_payments_booking_id",
            "booking_id",
            postgresql_where=text("booking_id IS NOT NULL"),
        ),
        Index(
            "uq_payments_salon_id_idempotency_key",
            "salon_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "uq_payments_provider_provider_payment_id",
            "provider",
            "provider_payment_id",
            unique=True,
            postgresql_where=text("provider_payment_id IS NOT NULL"),
        ),
    )
