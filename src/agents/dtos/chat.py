from dataclasses import dataclass
from datetime import datetime

MAX_CHAT_TITLE_LENGTH = 256
DEFAULT_CHAT_TITLE = 'Nova conversa'


@dataclass(frozen=True, slots=True)
class ChatDTO:
    id: int
    title: str
    project_id: int
    owner: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateChatDTO:
    project_id: int
    owner: int
    title: str = DEFAULT_CHAT_TITLE


@dataclass(frozen=True, slots=True)
class UpdateTitleChatDTO:
    title: str
