from datetime import datetime

from pydantic import BaseModel

from project.dtos.document import DocumentDTO
from project.entities.document import DocumentStatus
from project.utils.pagination import PageSchema


class DocumentSchema(BaseModel):
    id: int
    project_id: int
    file: str
    name: str
    description: str | None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: DocumentDTO) -> 'DocumentSchema':
        return cls(**{name: getattr(dto, name) for name in cls.model_fields})


class DocumentPageSchema(PageSchema[DocumentSchema]):
    items: list[DocumentSchema]
