from project.dtos.member import MemberDTO
from project.entities.member import MemberRole
from project.permissions.actions import DocumentAction
from project.permissions.authorization import PolicyDecision, ResourcePolicies
from project.permissions.dtos import DocumentPermissionDTO


def allow_document_create(
    member: MemberDTO,
    resource: DocumentPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_document_read(
    member: MemberDTO,
    resource: DocumentPermissionDTO,
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


def allow_document_update(
    member: MemberDTO,
    resource: DocumentPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_document_delete(
    member: MemberDTO,
    resource: DocumentPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (
        MemberRole.OWNER,
        MemberRole.DIRECTOR,
        MemberRole.MEMBER,
    ):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_document_approval(
    member: MemberDTO,
    resource: DocumentPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


def allow_document_tag_assignment(
    member: MemberDTO,
    resource: DocumentPermissionDTO,
    **context: object,
) -> PolicyDecision:
    if member.role in (MemberRole.OWNER, MemberRole.DIRECTOR):
        return PolicyDecision.ALLOW
    return PolicyDecision.NOT_APPLICABLE


DOCUMENT_POLICIES: ResourcePolicies[DocumentPermissionDTO, DocumentAction] = (
    ResourcePolicies()
    .register(DocumentAction.CREATE, allow_document_create)
    .register(DocumentAction.READ, allow_document_read)
    .register(DocumentAction.UPDATE, allow_document_update)
    .register(DocumentAction.DELETE, allow_document_delete)
    .register(DocumentAction.APPROVE, allow_document_approval)
    .register(DocumentAction.TAG_ASSIGN, allow_document_tag_assignment)
)
