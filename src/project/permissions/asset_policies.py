from project.dtos.member import MemberDTO
from project.entities.member import MemberRole
from project.permissions.actions import AssetAction
from project.permissions.authorization import PolicyDecision, ResourcePolicies
from project.permissions.dtos import AssetPermissionDTO


def allow_asset_create(
    member: MemberDTO,
    resource: AssetPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_asset_read(
    member: MemberDTO,
    resource: AssetPermissionDTO,
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


def allow_asset_update(
    member: MemberDTO,
    resource: AssetPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_asset_approval(
    member: MemberDTO,
    resource: AssetPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_asset_tag_assignment(
    member: MemberDTO,
    resource: AssetPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


ASSET_POLICIES: ResourcePolicies[AssetPermissionDTO, AssetAction] = (
    ResourcePolicies()
    .register(AssetAction.CREATE, allow_asset_create)
    .register(AssetAction.READ, allow_asset_read)
    .register(AssetAction.UPDATE, allow_asset_update)
    .register(AssetAction.APPROVE, allow_asset_approval)
    .register(AssetAction.TAG_ASSIGN, allow_asset_tag_assignment)
)
