from infra.logs import get_logger
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import CreateProjectDTO, ProjectDTO, UpdateProjectDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    InsufficientProjectPermissionException,
    ProjectNotFoundException,
)
from project.unit_of_work import IProjectUnitOfWork

logger = get_logger(__name__)


async def _active_member(
    uow: IProjectUnitOfWork, project_id: int, user_id: int
):
    page = await uow.member_repository.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    return page.items[0] if page.items else None


async def _require_project_member(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
):
    project = await uow.project_repository.get_project(project_id)
    member = await _active_member(uow, project_id, user_id)
    if project is None or member is None:
        logger.warning(
            'Project access denied because project or active membership '
            'was not found'
        )
        raise ProjectNotFoundException(project_id)
    return project, member


async def create_project(
    uow: IProjectUnitOfWork,
    owner_id: int,
    data: CreateProjectDTO,
) -> ProjectDTO:
    project = await uow.project_repository.create_project(data.name, owner_id)
    await uow.member_repository.create_member(
        project.id, owner_id, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    await uow.commit()
    logger.info(
        'Project created: project_id=%s owner_id=%s', project.id, owner_id
    )
    return project


async def get_projects(
    uow: IProjectUnitOfWork,
    user_id: int,
    name: str | None = None,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ProjectDTO]:
    page = await uow.project_repository.get_projects_for_member(
        user_id, name, pagination
    )
    logger.debug(
        'Project list loaded: user_id=%s count=%s', user_id, len(page.items)
    )
    return page


async def update_project(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    data: UpdateProjectDTO,
) -> ProjectDTO:
    _, member = await _require_project_member(uow, project_id, user_id)
    if member.role not in (MemberRole.OWNER, MemberRole.DIRECTOR):
        logger.warning(
            'Project update denied: project_id=%s user_id=%s',
            project_id,
            user_id,
        )
        raise InsufficientProjectPermissionException('project:update')
    updated = await uow.project_repository.update_project(
        project_id, name=data.name
    )
    if updated is None:
        raise ProjectNotFoundException(project_id)
    await uow.commit()
    logger.info(
        'Project updated: project_id=%s user_id=%s', project_id, user_id
    )
    return updated


async def delete_project(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
) -> None:
    _, member = await _require_project_member(uow, project_id, user_id)
    if member.role not in (MemberRole.OWNER):
        logger.warning(
            'Project deletion denied: project_id=%s user_id=%s',
            project_id,
            user_id,
        )
        raise InsufficientProjectPermissionException('project:delete')
    await uow.project_repository.delete_project(project_id)
    await uow.commit()
    logger.info(
        'Project deleted: project_id=%s user_id=%s', project_id, user_id
    )
