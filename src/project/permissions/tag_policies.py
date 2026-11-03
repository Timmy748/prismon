from project.dtos.member import MemberDTO
from project.entities.member import MemberRole
from project.permissions.actions import TagAction
from project.permissions.authorization import PolicyDecision, ResourcePolicies
from project.permissions.dtos import TagPermissionDTO


def allow_tag_read(
    member: MemberDTO,
    resource: TagPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
        MemberRole.COLLABORATOR,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_tag_create(
    member: MemberDTO,
    resource: TagPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_tag_update(
    member: MemberDTO,
    resource: TagPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_tag_delete(
    member: MemberDTO,
    resource: TagPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


TAG_POLICIES: ResourcePolicies[TagPermissionDTO, TagAction] = (
    ResourcePolicies()
    .register(TagAction.READ, allow_tag_read)
    .register(TagAction.CREATE, allow_tag_create)
    .register(TagAction.UPDATE, allow_tag_update)
    .register(TagAction.DELETE, allow_tag_delete)
)
