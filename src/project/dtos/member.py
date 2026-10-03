from dataclasses import dataclass
from datetime import datetime

from project.entities.member import MemberRole, MemberStatus


@dataclass(frozen=True, slots=True)
class InviteMemberDTO:
    email: str


@dataclass(frozen=True, slots=True)
class ResumeInviteMemberDTO:
    accept: bool


@dataclass(frozen=True, slots=True)
class ChangeRoleMemberDTO:
    new_role: str


@dataclass(frozen=True, slots=True)
class MemberDTO:
    id: int
    project_id: int
    role: MemberRole
    status: MemberStatus
    user_id: int
    created_at: datetime
    updated_at: datetime
