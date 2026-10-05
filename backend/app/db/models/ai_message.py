from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.ai_conversation import AIConversation
    from app.db.models.salon import Salon


def _ai_message_conversation_join():
    from app.db.models.ai_conversation import AIConversation

    return (
        (AIConversation.salon_id == AIMessage.salon_id)
        & (AIConversation.id == foreign(AIMessage.conversation_id))
    )


_AI_MESSAGE_ROLE_CHECK = (
    "role IN ('user', 'assistant', 'system', 'tool')"
)


class AIMessage(Base, UUIDPrimaryKeyMixin):
    """Messages within an AI conversation (user, assistant, tool results)."""

    __tablename__ = "ai_messages"

    salon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("salons.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    salon: Mapped[Salon] = relationship(back_populates="ai_messages")
    conversation: Mapped[AIConversation] = relationship(
        back_populates="messages",
        primaryjoin=_ai_message_conversation_join,
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["salon_id", "conversation_id"],
            ["ai_conversations.salon_id", "ai_conversations.id"],
            ondelete="CASCADE",
            name="fk_ai_messages_conversation_salon_id_conversation_id",
        ),
        CheckConstraint(_AI_MESSAGE_ROLE_CHECK, name="ck_ai_messages_role"),
        Index(
            "ix_ai_messages_salon_id_conversation_id_created_at",
            "salon_id",
            "conversation_id",
            "created_at",
        ),
        Index(
            "ix_ai_messages_salon_id_created_at",
            "salon_id",
            desc("created_at"),
        ),
    )
