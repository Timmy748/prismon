from project.dtos.member import MemberDTO
from project.entities.member import MemberStatus
from project.permissions.actions import MemberAction
from project.permissions.authorization import PolicyDecision, ResourcePolicies
from project.permissions.dtos import MemberPermissionDTO


def _respond_to_own_invitation(
    member: MemberDTO,
    resource: MemberPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if (
        member.user_id == resource.user_id
        and member.project_id == resource.project_id
        and resource.status is MemberStatus.PENDING
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


MEMBER_POLICIES: ResourcePolicies[MemberPermissionDTO, MemberAction] = (
    ResourcePolicies()
    .register(MemberAction.ACCEPT_INVITATION, _respond_to_own_invitation)
    .register(MemberAction.DECLINE_INVITATION, _respond_to_own_invitation)
)
