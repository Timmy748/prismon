from dataclasses import dataclass
from datetime import datetime

from project.entities.api_key import ApiKeyProvider


@dataclass(frozen=True, slots=True)
class ApiKeyHintDTO:
    id: int
    provider: ApiKeyProvider
    api_hint: str
    created_at: datetime
