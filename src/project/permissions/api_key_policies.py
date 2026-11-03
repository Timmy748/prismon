from project.dtos.member import MemberDTO
from project.permissions.actions import ApiKeyAction
from project.permissions.authorization import PolicyDecision, ResourcePolicies
from project.permissions.dtos import ApiKeyPermissionDTO


def _allow_member_api_key_operation(
    member: MemberDTO,
    resource: ApiKeyPermissionDTO,
    **context: object,
) -> PolicyDecision:
    return PolicyDecision.ALLOW


def _project_owner_only(
    member: MemberDTO,
    resource: ApiKeyPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if resource.project_id is None:
        return PolicyDecision.NOT_APPLICABLE
    if resource.project_owner_id == member.user_id:
        return PolicyDecision.ALLOW
    return PolicyDecision.DENY


def _read_owned_key(
    member: MemberDTO,
    resource: ApiKeyPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if resource.member_id is not None:
        if resource.project_id is None and resource.member_id == member.id:
            return PolicyDecision.ALLOW
        return PolicyDecision.NOT_APPLICABLE
    if resource.project_id == member.project_id:
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def _delete_owned_key(
    member: MemberDTO,
    resource: ApiKeyPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if resource.project_id is not None:
        if resource.project_id != member.project_id:
            return PolicyDecision.NOT_APPLICABLE
        if resource.project_owner_id == member.user_id:
            return PolicyDecision.ALLOW
        return PolicyDecision.DENY
    if resource.member_id == member.id:
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


API_KEY_POLICIES: ResourcePolicies[ApiKeyPermissionDTO, ApiKeyAction] = (
    ResourcePolicies()
    .register(ApiKeyAction.MEMBER_CREATE, _allow_member_api_key_operation)
    .register(ApiKeyAction.PROJECT_CREATE, _project_owner_only)
    .register(ApiKeyAction.MEMBER_LIST, _allow_member_api_key_operation)
    .register(ApiKeyAction.PROJECT_LIST, _allow_member_api_key_operation)
    .register(ApiKeyAction.READ, _read_owned_key)
    .register(ApiKeyAction.DELETE, _delete_owned_key)
)
