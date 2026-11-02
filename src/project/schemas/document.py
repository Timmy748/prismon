from datetime import datetime

from pydantic import BaseModel, Field

from project.dtos.document import DocumentDTO, DocumentUploadDTO
from project.dtos.resource_event import ResourceEventDTO
from project.entities.document import DocumentStatus
from project.schemas.tag import TagSchema
from project.utils.pagination import PageSchema


class StartDocumentUploadRequest(BaseModel):
    name: str
    original_filename: str = Field(min_length=1, max_length=512)
    description: str | None = None
    content_type: str = Field(
        default='application/octet-stream', max_length=256
    )


class ReplaceDocumentUploadRequest(BaseModel):
    original_filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(
        default='application/octet-stream', max_length=256
    )
    name: str | None = None
    description: str | None = None


class UpdateDocumentRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class DocumentSchema(BaseModel):
    id: int
    project_id: int
    file: str | None
    file_extension: str | None = None
    content_type: str | None = None
    created_by_member_id: int
    name: str
    description: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    tags: list[TagSchema] = Field(default_factory=list)

    @classmethod
    def from_dto(cls, dto: DocumentDTO) -> 'DocumentSchema':
        return cls(**{name: getattr(dto, name) for name in cls.model_fields})


class DocumentPageSchema(PageSchema[DocumentSchema]):
    items: list[DocumentSchema]


class DocumentUploadSchema(DocumentSchema):
    upload_url: str
    method: str = 'PUT'
    required_headers: dict[str, str]
    expires_at: datetime

    @classmethod
    def from_dto(cls, dto: DocumentUploadDTO) -> 'DocumentUploadSchema':
        return cls(
            **{
                name: getattr(dto.document, name)
                for name in DocumentSchema.model_fields
            },
            upload_url=dto.upload_url,
            required_headers=dto.required_headers,
            expires_at=dto.expires_at,
        )


class DocumentEventSchema(BaseModel):
    id: int
    project_id: int
    resource_type: str
    resource_id: int
    author_member_id: int
    event_type: str
    data: dict[str, object]
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: ResourceEventDTO) -> 'DocumentEventSchema':
        return cls(**{name: getattr(dto, name) for name in cls.model_fields})


class DocumentEventPageSchema(PageSchema[DocumentEventSchema]):
    items: list[DocumentEventSchema]
