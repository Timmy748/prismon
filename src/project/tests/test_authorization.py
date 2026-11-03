from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from project.dtos.member import MemberDTO
from project.entities.member import MemberRole, MemberStatus
from project.permissions.actions import (
    ApiKeyAction,
    AssetAction,
    ChatAction,
    DocumentAction,
    MemberAction,
    ProjectAction,
    TagAction,
)
from project.permissions.authorization import (
    PolicyDecision,
    ResourceActions,
    ResourcePolicies,
)
from project.permissions.dispatcher import verify_resource_permission
from project.permissions.dtos import (
    ApiKeyPermissionDTO,
    AssetPermissionDTO,
    DocumentPermissionDTO,
    MemberPermissionDTO,
    ProjectPermissionDTO,
    TagPermissionDTO,
)


@dataclass(frozen=True, slots=True)
class UnregisteredPermissionDTO:
    value: str


def _member(
    role: MemberRole,
    user_id: int = 1,
    status: MemberStatus = MemberStatus.ACTIVE,
) -> MemberDTO:
    now = datetime.now(UTC)
    return MemberDTO(
        id=10,
        project_id=20,
        role=role,
        status=status,
        user_id=user_id,
        created_at=now,
        updated_at=now,
    )


def test_explicit_deny_overrides_another_policy_allow():
    policies: ResourcePolicies[ProjectPermissionDTO, ProjectAction] = (
        ResourcePolicies()
    )

    def allow(member, resource, **context):
        return PolicyDecision.ALLOW

    def deny(member, resource, **context):
        return PolicyDecision.DENY

    policies.register(ProjectAction.UPDATE, allow)
    policies.register(ProjectAction.UPDATE, deny)

    result = policies.verify(
        _member(MemberRole.OWNER),
        ProjectPermissionDTO(project_id=20),
        ProjectAction.UPDATE,
    )

    assert result is False


def test_unregistered_action_denies_by_default():
    policies: ResourcePolicies[ProjectPermissionDTO, ProjectAction] = (
        ResourcePolicies()
    )

    result = policies.verify(
        _member(MemberRole.OWNER),
        ProjectPermissionDTO(project_id=20),
        ProjectAction.DELETE,
    )

    assert result is False


def test_not_applicable_policy_denies_by_default():
    policies: ResourcePolicies[ProjectPermissionDTO, ProjectAction] = (
        ResourcePolicies()
    )

    def not_applicable(member, resource, **context):
        return PolicyDecision.NOT_APPLICABLE

    policies.register(ProjectAction.UPDATE, not_applicable)

    result = policies.verify(
        _member(MemberRole.OWNER),
        ProjectPermissionDTO(project_id=20),
        ProjectAction.UPDATE,
    )

    assert result is False


def test_dispatcher_routes_by_permission_dto_type():
    result = verify_resource_permission(
        _member(MemberRole.DIRECTOR),
        ProjectPermissionDTO(project_id=20),
        ProjectAction.UPDATE,
    )

    assert result is True


def test_dispatcher_denies_unregistered_permission_dto_type():
    result = verify_resource_permission(
        _member(MemberRole.OWNER),
        UnregisteredPermissionDTO(value='unknown'),
        ProjectAction.UPDATE,
    )

    assert result is False


def test_project_policy_denies_director_project_deletion():
    result = verify_resource_permission(
        _member(MemberRole.DIRECTOR, user_id=2),
        ProjectPermissionDTO(project_id=20),
        ProjectAction.DELETE,
    )

    assert result is False


@pytest.mark.parametrize(
    ('role', 'action', 'expected'),
    [(MemberRole.OWNER, action, True) for action in ChatAction]
    + [(MemberRole.DIRECTOR, action, True) for action in ChatAction]
    + [(MemberRole.MEMBER, action, True) for action in ChatAction]
    + [
        (MemberRole.COLLABORATOR, action, action is ChatAction.READ)
        for action in ChatAction
    ],
)
def test_chat_action_policy_preserves_role_permissions(
    role: MemberRole, action: ChatAction, expected: bool
):
    result = verify_resource_permission(
        _member(role), ProjectPermissionDTO(project_id=20), action
    )

    assert result is expected


def test_policy_registration_does_not_match_another_action_enum():
    class OtherProjectAction(ResourceActions):
        UPDATE = 'project:update'

    result = verify_resource_permission(
        _member(MemberRole.OWNER),
        ProjectPermissionDTO(project_id=20),
        OtherProjectAction.UPDATE,
    )

    assert result is False


def test_resource_policy_receives_additional_context():
    policies: ResourcePolicies[ProjectPermissionDTO, ProjectAction] = (
        ResourcePolicies()
    )

    def allow_matching_project(
        member,
        resource,
        *,
        expected_project_id: int,
    ):
        if resource.project_id == expected_project_id:
            return PolicyDecision.ALLOW
        return PolicyDecision.NOT_APPLICABLE

    policies.register(ProjectAction.UPDATE, allow_matching_project)

    result = policies.verify(
        _member(MemberRole.MEMBER),
        ProjectPermissionDTO(project_id=20),
        ProjectAction.UPDATE,
        expected_project_id=20,
    )

    assert result is True


@pytest.mark.parametrize(
    ('resource', 'action', 'member'),
    [
        (
            ApiKeyPermissionDTO(None, None, 1),
            ApiKeyAction.PROJECT_CREATE,
            _member(MemberRole.OWNER),
        ),
        (
            ApiKeyPermissionDTO(21, None, 2),
            ApiKeyAction.DELETE,
            _member(MemberRole.OWNER),
        ),
        (
            ApiKeyPermissionDTO(None, 99, None),
            ApiKeyAction.DELETE,
            _member(MemberRole.OWNER),
        ),
        (
            AssetPermissionDTO(20),
            AssetAction.CREATE,
            _member(MemberRole.COLLABORATOR),
        ),
        (AssetPermissionDTO(20), AssetAction.READ, _member('unknown')),
        (
            AssetPermissionDTO(20),
            AssetAction.UPDATE,
            _member(MemberRole.MEMBER),
        ),
        (
            AssetPermissionDTO(20),
            AssetAction.TAG_ASSIGN,
            _member(MemberRole.MEMBER),
        ),
        (
            DocumentPermissionDTO(20),
            DocumentAction.READ,
            _member('unknown'),
        ),
        (
            DocumentPermissionDTO(20),
            DocumentAction.DELETE,
            _member(MemberRole.COLLABORATOR),
        ),
        (
            DocumentPermissionDTO(20),
            DocumentAction.APPROVE,
            _member(MemberRole.MEMBER),
        ),
        (
            AssetPermissionDTO(20),
            AssetAction.APPROVE,
            _member(MemberRole.MEMBER),
        ),
        (
            DocumentPermissionDTO(20),
            DocumentAction.CREATE,
            _member(MemberRole.COLLABORATOR),
        ),
        (
            DocumentPermissionDTO(20),
            DocumentAction.UPDATE,
            _member(MemberRole.MEMBER),
        ),
        (
            DocumentPermissionDTO(20),
            DocumentAction.TAG_ASSIGN,
            _member(MemberRole.MEMBER),
        ),
        (
            TagPermissionDTO(20),
            TagAction.CREATE,
            _member(MemberRole.MEMBER),
        ),
        (
            TagPermissionDTO(20),
            TagAction.UPDATE,
            _member(MemberRole.COLLABORATOR),
        ),
        (TagPermissionDTO(20), TagAction.READ, _member('unknown')),
        (
            TagPermissionDTO(20),
            TagAction.DELETE,
            _member(MemberRole.MEMBER),
        ),
        (
            MemberPermissionDTO(
                10, 20, 99, MemberRole.MEMBER, MemberStatus.PENDING
            ),
            MemberAction.ACCEPT_INVITATION,
            _member(MemberRole.MEMBER),
        ),
        (
            ProjectPermissionDTO(20),
            ProjectAction.MEMBER_LIST,
            _member(MemberRole.MEMBER, status=MemberStatus.REMOVED),
        ),
        (
            ProjectPermissionDTO(20),
            ChatAction.READ,
            _member(MemberRole.MEMBER, status=MemberStatus.PENDING),
        ),
    ],
)
def test_policies_deny_when_role_scope_or_status_does_not_apply(
    resource, action, member
):
    assert verify_resource_permission(member, resource, action) is False
