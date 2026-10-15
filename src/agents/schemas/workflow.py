from datetime import datetime

from pydantic import BaseModel, ConfigDict

from agents.dtos.workflow import WorkflowDTO


class WorkflowSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    picture: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, workflow: WorkflowDTO) -> 'WorkflowSchema':
        return cls(
            id=workflow.id,
            name=workflow.name,
            description=workflow.description,
            picture=workflow.picture,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )
