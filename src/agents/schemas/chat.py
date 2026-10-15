from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agents.dtos.chat import MAX_CHAT_TITLE_LENGTH, ChatDTO


class ChatSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    project_id: int
    owner: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, chat: ChatDTO) -> 'ChatSchema':
        return cls(
            id=chat.id,
            title=chat.title,
            project_id=chat.project_id,
            owner=chat.owner,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
        )


class UpdateChatTitleSchema(BaseModel):
    title: str = Field(max_length=MAX_CHAT_TITLE_LENGTH)
