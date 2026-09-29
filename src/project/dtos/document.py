from dataclasses import dataclass
from datetime import datetime

from project.entities.document import DocumentStatus


@dataclass(frozen=True, slots=True)
class DocumentDTO:
    id: int
    project_id: int
    file: str
    name: str
    description: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateDocumentDTO:
    file: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class UpdateDocumentDTO:
    file: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ApproveDocumentDTO:
    accept: bool
