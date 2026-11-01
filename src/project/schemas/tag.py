from pydantic import BaseModel, ConfigDict, Field

from project.dtos.tag import TagDTO


class TagSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    label: str
    description: str
    color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')

    @classmethod
    def from_dto(cls, dto: TagDTO) -> 'TagSchema':
        return cls(**{name: getattr(dto, name) for name in cls.model_fields})


class CreateTagSchema(BaseModel):
    label: str = Field(min_length=1, max_length=128)
    description: str = Field(max_length=256)
    color: str = Field(pattern=r'^#[0-9A-Fa-f]{6}$')


class UpdateTagSchema(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=256)
    color: str | None = Field(default=None, pattern=r'^#[0-9A-Fa-f]{6}$')


class TagListSchema(BaseModel):
    items: list[TagSchema]
