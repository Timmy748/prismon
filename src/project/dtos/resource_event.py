from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ResourceEventDTO:
    id: int
    project_id: int
    resource_type: str
    resource_id: int
    author_member_id: int
    event_type: str
    data: dict[str, Any]
    idempotency_key: str | None
    created_at: datetime
