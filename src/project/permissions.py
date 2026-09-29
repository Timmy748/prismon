from enum import Enum
from typing import Protocol

from project.entities.member import MemberRole


class ProjectPermission(str, Enum):
    CHAT_READ = 'chat:read'
    CHAT_CREATE = 'chat:create'
    CHAT_DELETE = 'chat:delete'
    CHAT_UPDATE = 'chat:update'
    CHAT_SEND_MESSAGE = 'chat:send_message'
    MEMBER_INVITE = 'member:invite'
    MEMBER_REMOVE = 'member:remove'
    MEMBER_APPROVE = 'member:approve'
    MEMBER_CHANGE_ROLE = 'member:change_role'
    DOCUMENT_CREATE = 'document:create'
    DOCUMENT_READ = 'document:read'
    DOCUMENT_DELETE = 'document:delete'
    DOCUMENT_UPDATE = 'document:update'
    DOCUMENT_APPROVE = 'document:approve'
    ASSET_CREATE = 'asset:create'
    ASSET_READ = 'asset:read'
    ASSET_UPDATE = 'asset:update'
    ASSET_APPROVE = 'asset:approve'
    WORKFLOW_USE = 'workflow:use'


class PermissionCheckCallback(Protocol):
    def __call__(
        self, role: MemberRole, permission: ProjectPermission
    ) -> bool: ...


_ROLE_PERMISSIONS: dict[MemberRole, frozenset[ProjectPermission]] = {
    MemberRole.OWNER: frozenset(ProjectPermission),
    MemberRole.DIRECTOR: frozenset(ProjectPermission),
    MemberRole.MEMBER: frozenset(
        {
            ProjectPermission.CHAT_READ,
            ProjectPermission.CHAT_CREATE,
            ProjectPermission.CHAT_DELETE,
            ProjectPermission.CHAT_UPDATE,
            ProjectPermission.CHAT_SEND_MESSAGE,
            ProjectPermission.DOCUMENT_CREATE,
            ProjectPermission.DOCUMENT_READ,
            ProjectPermission.DOCUMENT_DELETE,
            ProjectPermission.ASSET_CREATE,
            ProjectPermission.ASSET_READ,
        }
    ),
    MemberRole.COLLABORATOR: frozenset(
        {
            ProjectPermission.WORKFLOW_USE,
            ProjectPermission.CHAT_READ,
            ProjectPermission.DOCUMENT_READ,
            ProjectPermission.ASSET_READ,
        }
    ),
}


def has_permission(role: MemberRole, permission: ProjectPermission) -> bool:
    return permission in _ROLE_PERMISSIONS[role]
