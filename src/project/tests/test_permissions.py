import pytest

from project.entities.member import MemberRole
from project.permissions import ProjectPermission, has_permission


@pytest.mark.parametrize(
    ('role', 'permissions'),
    [
        (MemberRole.OWNER, set(ProjectPermission)),
        (MemberRole.DIRECTOR, set(ProjectPermission)),
        (
            MemberRole.MEMBER,
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
            },
        ),
        (
            MemberRole.COLLABORATOR,
            {
                ProjectPermission.WORKFLOW_USE,
                ProjectPermission.CHAT_READ,
                ProjectPermission.DOCUMENT_READ,
                ProjectPermission.ASSET_READ,
            },
        ),
    ],
)
def test_has_permission_returns_role_permission_membership(
    role: MemberRole, permissions: set[ProjectPermission]
) -> None:
    for permission in ProjectPermission:
        assert has_permission(role, permission) == (permission in permissions)
