from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.ai_message import AIMessage
    from app.db.models.customer import Customer
    from app.db.models.salon import Salon
    from app.db.models.user import User


def _ai_conversation_customer_join():
    from app.db.models.customer import Customer

    return (
        (AIConversation.salon_id == Customer.salon_id)
        & (Customer.id == foreign(AIConversation.customer_id))
    )


def _ai_conversation_messages_join():
    from app.db.models.ai_message import AIMessage

    return (
        (AIMessage.salon_id == AIConversation.salon_id)
        & (AIConversation.id == foreign(AIMessage.conversation_id))
    )


class AIConversation(Base, UUIDPrimaryKeyMixin):
    """Audit log of AI assistant sessions in salon context."""

    __tablename__ = "ai_conversations"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    channel: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="dashboard",
    )
    external_thread_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(back_populates="ai_conversations")
    user: Mapped[User | None] = relationship(back_populates="ai_conversations")
    customer: Mapped[Customer | None] = relationship(
        back_populates="ai_conversations",
        primaryjoin=_ai_conversation_customer_join,
    )
    messages: Mapped[list[AIMessage]] = relationship(
        back_populates="conversation",
        primaryjoin=_ai_conversation_messages_join,
    )

    __table_args__ = (
        UniqueConstraint("salon_id", "id", name="uq_ai_conversations_salon_id_id"),
        ForeignKeyConstraint(
            ["salon_id", "customer_id"],
            ["customers.salon_id", "customers.id"],
            ondelete="SET NULL",
            name="fk_ai_conversations_customer_salon_id_customer_id",
        ),
        Index(
            "ix_ai_conversations_salon_id_last_message_at",
            "salon_id",
            desc("last_message_at").nulls_last(),
        ),
        Index(
            "ix_ai_conversations_salon_id_user_id",
            "salon_id",
            "user_id",
        ),
        Index(
            "ix_ai_conversations_external_thread_id",
            "external_thread_id",
            postgresql_where=text("external_thread_id IS NOT NULL"),
        ),
    )
