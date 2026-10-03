from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    created_at: datetime
    updated_at: datetime


class CreateProjectSchema(BaseModel):
    name: str


class UpdateProjectSchema(BaseModel):
    name: str | None = None
