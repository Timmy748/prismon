from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from agents.entities.message import SenderType


@dataclass(frozen=True, slots=True)
class MessageDTO:
    id: int
    chat_id: int
    parent_id: Optional[int]
    sender_type: SenderType
    text: str
    payload: dict[str, Any]
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateMessageDTO:
    parent_id: Optional[int]
    sender_type: SenderType
    text: str
    payload: dict[str, Any]
    meta_data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UpdateMessageDTO:
    text: str
    payload: dict[str, Any]
