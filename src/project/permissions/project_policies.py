from project.dtos.member import MemberDTO
from project.entities.member import MemberRole, MemberStatus
from project.permissions.actions import ChatAction, ProjectAction
from project.permissions.authorization import (
    PolicyDecision,
    ResourceActions,
    ResourcePolicies,
)
from project.permissions.dtos import ProjectPermissionDTO


def allow_project_update(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_project_delete(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role is MemberRole.OWNER:
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_member_list(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.status is MemberStatus.ACTIVE:
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_member_invite(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_member_role_change(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_member_remove(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_chat_create(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_chat_read(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.status is MemberStatus.ACTIVE:
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_chat_delete(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_chat_update(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_chat_message_send(
    member: MemberDTO,
    resource: ProjectPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


PROJECT_POLICIES: ResourcePolicies[ProjectPermissionDTO, ResourceActions] = (
    ResourcePolicies()
    .register(ProjectAction.UPDATE, allow_project_update)
    .register(ProjectAction.DELETE, allow_project_delete)
    .register(ProjectAction.MEMBER_LIST, allow_member_list)
    .register(ProjectAction.MEMBER_INVITE, allow_member_invite)
    .register(ProjectAction.MEMBER_CHANGE_ROLE, allow_member_role_change)
    .register(ProjectAction.MEMBER_REMOVE, allow_member_remove)
    .register(ChatAction.CREATE, allow_chat_create)
    .register(ChatAction.READ, allow_chat_read)
    .register(ChatAction.DELETE, allow_chat_delete)
    .register(ChatAction.UPDATE, allow_chat_update)
    .register(ChatAction.SEND_MESSAGE, allow_chat_message_send)
)
