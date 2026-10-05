from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Uuid,
    desc,
    func,
    text,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.customer import Customer
    from app.db.models.salon import Salon
    from app.db.models.user import User

_TRANSACTION_TYPE_CHECK = (
    "transaction_type IN ('earn', 'redeem', 'adjustment', 'expire', 'refund')"
)

_AMOUNT_SIGN_CHECK = (
    "((transaction_type = 'redeem' AND amount_cents <= 0) OR "
    "(transaction_type = 'earn' AND amount_cents >= 0) OR "
    "transaction_type IN ('adjustment', 'expire', 'refund'))"
)


def _bonus_transaction_customer_join():
    from app.db.models.customer import Customer

    return (
        (Customer.salon_id == BonusTransaction.salon_id)
        & (Customer.id == foreign(BonusTransaction.customer_id))
    )


def _bonus_transaction_booking_join():
    from app.db.models.booking import Booking

    return (
        (Booking.salon_id == BonusTransaction.salon_id)
        & (Booking.id == foreign(BonusTransaction.booking_id))
    )


class BonusTransaction(Base, UUIDPrimaryKeyMixin):
    """Append-only salon-scoped loyalty ledger per customer."""

    __tablename__ = "bonus_transactions"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(back_populates="bonus_transactions")
    customer: Mapped[Customer] = relationship(
        back_populates="bonus_transactions",
        primaryjoin=_bonus_transaction_customer_join,
    )
    booking: Mapped[Booking | None] = relationship(
        back_populates="bonus_transactions",
        primaryjoin=_bonus_transaction_booking_join,
    )
    created_by_user: Mapped[User | None] = relationship(
        back_populates="bonus_transactions_created",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="RESTRICT",
            name="fk_bonus_transactions_customer_salon_id_customer_id",
        ),
        ForeignKeyConstraint(
            ["salon_id", "booking_id"],
            ["bookings.salon_id", "bookings.id"],
            ondelete="SET NULL",
            name="fk_bonus_transactions_booking_salon_id_booking_id",
        ),
        CheckConstraint(
            _TRANSACTION_TYPE_CHECK,
            name="ck_bonus_transactions_transaction_type",
        ),
        CheckConstraint(
            _AMOUNT_SIGN_CHECK,
            name="ck_bonus_transactions_amount_sign",
        ),
        Index(
            "ix_bonus_transactions_salon_id_customer_id_created_at",
            "salon_id",
            "customer_id",
            desc("created_at"),
        ),
        Index(
            "ix_bonus_transactions_booking_id",
            "booking_id",
            postgresql_where=text("booking_id IS NOT NULL"),
        ),
        Index(
            "uq_bonus_transactions_salon_id_idempotency_key",
            "salon_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )
