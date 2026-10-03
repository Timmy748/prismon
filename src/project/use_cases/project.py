from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import CreateProjectDTO, ProjectDTO, UpdateProjectDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    InsufficientProjectPermissionException,
    ProjectNotFoundException,
)
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository


async def _active_member(
    member_repo: IMemberRepository, project_id: int, user_id: int
):
    page = await member_repo.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    return page.items[0] if page.items else None


async def _require_project_member(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    user_id: int,
):
    project = await project_repo.get_project(project_id)
    member = await _active_member(member_repo, project_id, user_id)
    if project is None or member is None:
        raise ProjectNotFoundException(project_id)
    return project, member


async def create_project(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    owner_id: int,
    data: CreateProjectDTO,
) -> ProjectDTO:
    project = await project_repo.create_project(data.name, owner_id)
    await member_repo.create_member(
        project.id, owner_id, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    return project


async def get_projects(
    project_repo: IProjectRepository,
    user_id: int,
    name: str | None = None,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ProjectDTO]:
    return await project_repo.get_projects_for_member(user_id, name, pagination)


async def update_project(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    user_id: int,
    data: UpdateProjectDTO,
) -> ProjectDTO:
    _, member = await _require_project_member(
        project_repo, member_repo, project_id, user_id
    )
    if member.role not in (MemberRole.OWNER, MemberRole.DIRECTOR):
        raise InsufficientProjectPermissionException('project:update')
    updated = await project_repo.update_project(project_id, name=data.name)
    if updated is None:
        raise ProjectNotFoundException(project_id)
    return updated


async def delete_project(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    user_id: int,
) -> None:
    _, member = await _require_project_member(
        project_repo, member_repo, project_id, user_id
    )
    if member.role not in (MemberRole.OWNER):
        raise InsufficientProjectPermissionException('project:delete')
    await project_repo.delete_project(project_id)
