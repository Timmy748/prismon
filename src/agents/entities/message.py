from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from agents.entities.registry import mapper_registry


class SenderType(str, Enum):
    ASSISTANT = 'assistant'
    USER = 'user'


@mapper_registry.mapped_as_dataclass
class Message:
    __tablename__ = 'messages'
    __table_args__ = (
        Index(
            'ix_messages_chat_created_at_id',
            'chat_id',
            'created_at',
            'id',
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    chat_id: Mapped[int] = mapped_column(
        ForeignKey('chats.id', ondelete='CASCADE')
    )
    text: Mapped[str] = mapped_column(Text())
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('messages.id', ondelete='CASCADE'), index=True
    )
    sender_type: Mapped[SenderType]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    meta_data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), insert_default=func.now(), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=func.now(),
        onupdate=func.now(),
        init=False,
    )
