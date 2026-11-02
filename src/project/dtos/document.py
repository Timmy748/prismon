from dataclasses import dataclass, field
from datetime import datetime

from project.dtos.tag import TagDTO
from project.entities.document import DocumentStatus


@dataclass(frozen=True, slots=True)
class DocumentDTO:
    id: int
    project_id: int
    created_by_member_id: int
    file: str | None
    name: str
    description: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    tags: list[TagDTO] = field(default_factory=list)
    file_extension: str | None = None
    content_type: str | None = None


@dataclass(frozen=True, slots=True)
class CreateDocumentDTO:
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class StartDocumentUploadDTO:
    name: str
    description: str = ''
    content_type: str = 'application/octet-stream'
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentUploadDTO:
    document: DocumentDTO
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]


@dataclass(frozen=True, slots=True)
class DocumentUploadCompletionDTO:
    document_id: int | None
    obsolete_file_key: str | None
    already_completed: bool
    ignored: bool = False


@dataclass(frozen=True, slots=True)
class UpdateDocumentDTO:
    file: str | None = None
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ApproveDocumentDTO:
    accept: bool
