# ruff: noqa: PLR0913, PLR0917
from project.dtos.member import (
    ChangeRoleMemberDTO,
    MemberDTO,
    ResumeInviteMemberDTO,
)
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    InsufficientProjectPermissionException,
    InvalidInvitationStateException,
    MemberAlreadyExistsException,
    MemberNotFoundException,
    ProjectNotFoundException,
)
from project.permissions import ProjectPermission, has_permission
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.use_cases.project import _require_project_member


def _require_permission(
    role: MemberRole, permission: ProjectPermission
) -> None:
    if not has_permission(role, permission):
        raise InsufficientProjectPermissionException(permission.value)


async def get_members(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[MemberDTO]:
    await _require_project_member(
        project_repo, member_repo, project_id, user_id
    )
    return await member_repo.get_members(project_id, pagination)


async def invite_member(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    actor_user_id: int,
    invited_user_id: int,
) -> MemberDTO:
    _, actor = await _require_project_member(
        project_repo, member_repo, project_id, actor_user_id
    )
    _require_permission(actor.role, ProjectPermission.MEMBER_INVITE)
    existing = await member_repo.get_members(
        project_id,
        PaginationDTO(limit=100),
        user_id=invited_user_id,
    )
    if existing.items:
        raise MemberAlreadyExistsException(project_id, invited_user_id)
    created = await member_repo.create_member(
        project_id, invited_user_id, MemberRole.MEMBER, MemberStatus.PENDING
    )
    if created is None:
        raise MemberNotFoundException(invited_user_id)
    return created


async def change_member_role(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    actor_user_id: int,
    member_id: int,
    data: ChangeRoleMemberDTO,
) -> MemberDTO:
    _, actor = await _require_project_member(
        project_repo, member_repo, project_id, actor_user_id
    )
    _require_permission(actor.role, ProjectPermission.MEMBER_CHANGE_ROLE)
    target = await member_repo.get_member(member_id)
    if target is None or target.project_id != project_id:
        raise MemberNotFoundException(member_id)
    try:
        role = MemberRole(data.new_role)
    except ValueError as exc:
        raise ValueError(f'Invalid member role: {data.new_role}') from exc
    updated = await member_repo.update_member(member_id, role=role)
    if updated is None:
        raise MemberNotFoundException(member_id)
    return updated


async def respond_to_invitation(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    user_id: int,
    data: ResumeInviteMemberDTO,
) -> MemberDTO:
    if await project_repo.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    page = await member_repo.get_members(
        project_id,
        PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.PENDING,
    )
    if not page.items:
        raise InvalidInvitationStateException(project_id, user_id)
    invitation = page.items[0]
    if not data.accept:
        await member_repo.delete_member(invitation.id)
        return invitation
    updated = await member_repo.update_member(
        invitation.id, status=MemberStatus.ACTIVE
    )
    if updated is None:
        raise InvalidInvitationStateException(project_id, user_id)
    return updated


async def remove_member(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    actor_user_id: int,
    member_id: int,
) -> None:
    _, actor = await _require_project_member(
        project_repo, member_repo, project_id, actor_user_id
    )
    _require_permission(actor.role, ProjectPermission.MEMBER_REMOVE)
    target = await member_repo.get_member(member_id)
    if target is None or target.project_id != project_id:
        raise MemberNotFoundException(member_id)
    await member_repo.delete_member(member_id)
