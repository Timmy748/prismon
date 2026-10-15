from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WorkflowDTO:
    id: int
    name: str
    description: str
    picture: str
    created_at: datetime
    updated_at: datetime
