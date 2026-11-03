from dataclasses import dataclass

from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus


@dataclass(frozen=True, slots=True)
class ProjectPermissionDTO:
    project_id: int


@dataclass(frozen=True, slots=True)
class MemberPermissionDTO:
    id: int
    project_id: int
    user_id: int
    role: MemberRole
    status: MemberStatus


@dataclass(frozen=True, slots=True)
class DocumentPermissionDTO:
    project_id: int
    status: DocumentStatus | None = None
    created_by_member_id: int | None = None


@dataclass(frozen=True, slots=True)
class AssetPermissionDTO:
    project_id: int
    status: AssetStatus | None = None
    created_by_member_id: int | None = None


@dataclass(frozen=True, slots=True)
class TagPermissionDTO:
    project_id: int


@dataclass(frozen=True, slots=True)
class ApiKeyPermissionDTO:
    project_id: int | None
    member_id: int | None
    project_owner_id: int | None
