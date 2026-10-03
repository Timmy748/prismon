from datetime import datetime

from pydantic import BaseModel, ConfigDict

from project.entities.member import MemberRole, MemberStatus


class MemberSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    user_id: int
    role: MemberRole
    status: MemberStatus
    created_at: datetime
    updated_at: datetime


class InviteMemberSchema(BaseModel):
    user_id: int


class ChangeMemberRoleSchema(BaseModel):
    new_role: str
