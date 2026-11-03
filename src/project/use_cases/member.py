# ruff: noqa: PLR0913, PLR0917
from infra.logs import get_logger
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
    InvalidMemberRoleException,
    MemberAlreadyExistsException,
    MemberNotFoundException,
    ProjectNotFoundException,
)
from project.permissions.actions import MemberAction, ProjectAction
from project.permissions.dispatcher import verify_resource_permission
from project.permissions.dtos import MemberPermissionDTO, ProjectPermissionDTO
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.project import _require_project_member

logger = get_logger(__name__)


async def get_members(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[MemberDTO]:
    _, member = await _require_project_member(uow, project_id, user_id)
    if not verify_resource_permission(
        member,
        ProjectPermissionDTO(project_id),
        ProjectAction.MEMBER_LIST,
    ):
        raise InsufficientProjectPermissionException(
            ProjectAction.MEMBER_LIST.value
        )
    page = await uow.member_repository.get_members(project_id, pagination)
    logger.debug(
        'Project members loaded: project_id=%s count=%s',
        project_id,
        len(page.items),
    )
    return page


async def invite_member(
    uow: IProjectUnitOfWork,
    project_id: int,
    actor_user_id: int,
    invited_user_id: int,
) -> MemberDTO:
    _, actor = await _require_project_member(uow, project_id, actor_user_id)
    if not verify_resource_permission(
        actor,
        ProjectPermissionDTO(project_id),
        ProjectAction.MEMBER_INVITE,
    ):
        logger.warning(
            'Member permission denied: permission=%s',
            ProjectAction.MEMBER_INVITE.value,
        )
        raise InsufficientProjectPermissionException(
            ProjectAction.MEMBER_INVITE.value
        )
    existing = await uow.member_repository.get_members(
        project_id,
        PaginationDTO(limit=100),
        user_id=invited_user_id,
    )
    if existing.items:
        raise MemberAlreadyExistsException(project_id, invited_user_id)
    created = await uow.member_repository.create_member(
        project_id, invited_user_id, MemberRole.MEMBER, MemberStatus.PENDING
    )
    if created is None:
        raise MemberNotFoundException(invited_user_id)
    await uow.commit()
    logger.info(
        'Project member invited: project_id=%s invited_user_id=%s',
        project_id,
        invited_user_id,
    )
    return created


async def change_member_role(
    uow: IProjectUnitOfWork,
    project_id: int,
    actor_user_id: int,
    member_id: int,
    data: ChangeRoleMemberDTO,
) -> MemberDTO:
    _, actor = await _require_project_member(uow, project_id, actor_user_id)
    if not verify_resource_permission(
        actor,
        ProjectPermissionDTO(project_id),
        ProjectAction.MEMBER_CHANGE_ROLE,
    ):
        raise InsufficientProjectPermissionException(
            ProjectAction.MEMBER_CHANGE_ROLE.value
        )
    target = await uow.member_repository.get_member(member_id)
    if target is None or target.project_id != project_id:
        raise MemberNotFoundException(member_id)
    try:
        role = MemberRole(data.new_role)
    except ValueError as exc:
        raise InvalidMemberRoleException(data.new_role) from exc
    updated = await uow.member_repository.update_member(member_id, role=role)
    if updated is None:
        raise MemberNotFoundException(member_id)
    await uow.commit()
    logger.info(
        'Project member role changed: project_id=%s member_id=%s',
        project_id,
        member_id,
    )
    return updated


async def respond_to_invitation(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    data: ResumeInviteMemberDTO,
) -> MemberDTO:
    if await uow.project_repository.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    page = await uow.member_repository.get_members(
        project_id,
        PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.PENDING,
    )
    if not page.items:
        raise InvalidInvitationStateException(project_id, user_id)
    invitation = page.items[0]
    member_action = (
        MemberAction.ACCEPT_INVITATION
        if data.accept
        else MemberAction.DECLINE_INVITATION
    )
    if not verify_resource_permission(
        invitation,
        MemberPermissionDTO(
            invitation.id,
            invitation.project_id,
            invitation.user_id,
            invitation.role,
            invitation.status,
        ),
        member_action,
    ):
        raise InvalidInvitationStateException(project_id, user_id)
    if not data.accept:
        await uow.member_repository.delete_member(invitation.id)
        await uow.commit()
        logger.info(
            'Project invitation declined: project_id=%s user_id=%s',
            project_id,
            user_id,
        )
        return invitation
    updated = await uow.member_repository.update_member(
        invitation.id, status=MemberStatus.ACTIVE
    )
    if updated is None:
        raise InvalidInvitationStateException(project_id, user_id)
    await uow.commit()
    logger.info(
        'Project invitation accepted: project_id=%s user_id=%s',
        project_id,
        user_id,
    )
    return updated


async def remove_member(
    uow: IProjectUnitOfWork,
    project_id: int,
    actor_user_id: int,
    member_id: int,
) -> None:
    _, actor = await _require_project_member(uow, project_id, actor_user_id)
    if not verify_resource_permission(
        actor,
        ProjectPermissionDTO(project_id),
        ProjectAction.MEMBER_REMOVE,
    ):
        raise InsufficientProjectPermissionException(
            ProjectAction.MEMBER_REMOVE.value
        )
    target = await uow.member_repository.get_member(member_id)
    if target is None or target.project_id != project_id:
        raise MemberNotFoundException(member_id)
    updated = await uow.member_repository.update_member(
        member_id, status=MemberStatus.REMOVED
    )
    if updated is None:
        raise MemberNotFoundException(member_id)
    await uow.commit()
    logger.info(
        'Project member removed: project_id=%s member_id=%s',
        project_id,
        member_id,
    )
