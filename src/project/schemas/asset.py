from datetime import datetime

from pydantic import BaseModel, Field

from project.dtos.asset import AssetDTO, AssetUploadDTO
from project.dtos.resource_event import ResourceEventDTO
from project.entities.asset import AssetStatus
from project.schemas.tag import TagSchema
from project.utils.pagination import PageSchema


class StartAssetUploadRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    type: str
    original_filename: str = Field(min_length=1, max_length=512)
    description: str | None = None
    content_type: str = Field(
        default='application/octet-stream', max_length=256
    )


class ReplaceAssetUploadRequest(BaseModel):
    original_filename: str = Field(min_length=1, max_length=512)
    content_type: str = Field(
        default='application/octet-stream', max_length=256
    )


class UpdateAssetRequest(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    type: str | None = None
    description: str | None = None


class AssetSchema(BaseModel):
    id: int
    project_id: int
    created_by_member_id: int
    file: str | None
    name: str
    file_extension: str | None = None
    content_type: str | None = None
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


class AssetUploadSchema(AssetSchema):
    upload_url: str
    method: str = 'PUT'
    required_headers: dict[str, str]
    expires_at: datetime

    @classmethod
    def from_dto(cls, dto: AssetUploadDTO) -> 'AssetUploadSchema':
        return cls(
            **{
                name: getattr(dto.asset, name)
                for name in AssetSchema.model_fields
            },
            upload_url=dto.upload_url,
            required_headers=dto.required_headers,
            expires_at=dto.expires_at,
        )


class AssetEventSchema(BaseModel):
    id: int
    project_id: int
    resource_type: str
    resource_id: int
    author_member_id: int
    event_type: str
    data: dict[str, object]
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: ResourceEventDTO) -> 'AssetEventSchema':
        return cls(**{name: getattr(dto, name) for name in cls.model_fields})


class AssetEventPageSchema(PageSchema[AssetEventSchema]):
    items: list[AssetEventSchema]
