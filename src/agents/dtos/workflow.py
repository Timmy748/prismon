from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class WorkflowDTO:
    id: int
    name: str
    description: str
    version: str
    created_at: datetime
    updated_at: datetime
    config: dict[str, Any] = field(default_factory=dict)
