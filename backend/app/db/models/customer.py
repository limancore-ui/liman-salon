from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.booking import Booking
    from app.db.models.bonus_transaction import BonusTransaction
    from app.db.models.ai_conversation import AIConversation
    from app.db.models.notification import Notification
    from app.db.models.review import Review
    from app.db.models.salon import Salon
    from app.db.models.user import User


class Customer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Salon-scoped customer profile (walk-in and registered guests)."""

    __tablename__ = "customers"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    bonus_balance_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    marketing_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    whatsapp_opt_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    salon: Mapped[Salon] = relationship(back_populates="customers")
    user: Mapped[User | None] = relationship(back_populates="customers")
    bookings: Mapped[list[Booking]] = relationship(back_populates="customer")
    bonus_transactions: Mapped[list[BonusTransaction]] = relationship(
        back_populates="customer",
    )
    reviews: Mapped[list[Review]] = relationship(back_populates="customer")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="customer",
    )
    ai_conversations: Mapped[list[AIConversation]] = relationship(
        back_populates="customer",
    )

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_customers_salon_id_id"),
        CheckConstraint(
            "bonus_balance_cents >= 0",
            name="ck_customers_bonus_balance_cents",
        ),
        Index(
            "uq_customers_salon_id_email_lower",
            "salon_id",
            func.lower(email),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_customers_salon_id_full_name", "salon_id", "full_name"),
        Index("ix_customers_salon_id_phone", "salon_id", "phone"),
        Index(
            "ix_customers_user_id",
            "user_id",
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )
