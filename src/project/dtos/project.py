from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ProjectDTO:
    id: int
    name: str
    owner_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateProjectDTO:
    name: str
    owner: str


@dataclass(frozen=True, slots=True)
class UpdateProjectDTO:
    name: str | None = None


@dataclass(frozen=True, slots=True)
class ChangeOwnerProjectDTO:
    new_owner: str
