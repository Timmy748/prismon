from datetime import datetime
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from agents.dtos.message import MessageDTO
from agents.entities.message import SenderType


class MessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    parent_id: int | None
    sender_type: SenderType
    text: str
    payload: dict[str, Any]
    meta_data: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, message: MessageDTO) -> 'MessageSchema':
        return cls(
            id=message.id,
            chat_id=message.chat_id,
            parent_id=message.parent_id,
            sender_type=message.sender_type,
            text=message.text,
            payload=message.payload,
            meta_data=message.meta_data,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )


class CreateMessageSchema(BaseModel):
    chat_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    api_key_id: int = Field(gt=0)
    text: str

    @field_validator('text')
    @classmethod
    def validate_text(cls, value: str) -> str:  # pragma: no cover
        if not value.strip():
            raise ValueError('Message text cannot be empty')
        return value

    @model_validator(mode='after')
    def require_project_for_new_chat(self) -> Self:  # pragma: no cover
        if self.chat_id is None and self.project_id is None:
            raise ValueError('project_id is required when chat_id is omitted')
        return self
