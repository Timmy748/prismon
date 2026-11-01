from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TagDTO:
    id: int
    project_id: int
    label: str
    description: str
    color: str


@dataclass(frozen=True, slots=True)
class CreateTagDTO:
    label: str
    description: str
    color: str


@dataclass(frozen=True, slots=True)
class UpdateTagDTO:
    label: str | None = None
    description: str | None = None
    color: str | None = None
