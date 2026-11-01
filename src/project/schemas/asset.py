from datetime import datetime

from pydantic import BaseModel, Field

from project.dtos.asset import AssetDTO
from project.entities.asset import AssetStatus
from project.schemas.tag import TagSchema
from project.utils.pagination import PageSchema


class AssetSchema(BaseModel):
    id: int
    project_id: int
    file: str
    type: str
    description: str | None
    status: AssetStatus
    created_at: datetime
    updated_at: datetime
    tags: list[TagSchema] = Field(default_factory=list)

    @classmethod
    def from_dto(cls, dto: AssetDTO) -> 'AssetSchema':
        return cls(**{name: getattr(dto, name) for name in cls.model_fields})


class AssetPageSchema(PageSchema[AssetSchema]):
    items: list[AssetSchema]
