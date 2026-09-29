from unittest.mock import AsyncMock

import pytest

from project.dtos.page import PaginationDTO
from project.dtos.project import CreateProjectDTO, UpdateProjectDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    InsufficientProjectPermissionException,
    ProjectNotFoundException,
)
from project.use_cases.project import (
    create_project,
    delete_project,
    get_projects,
    update_project,
)


@pytest.mark.asyncio
async def test_create_project_creates_active_owner(project_repo, member_repo):
    result = await create_project(
        project_repo, member_repo, 11, CreateProjectDTO('Brand', 'ignored')
    )
    members = await member_repo.get_members(result.id)
    assert result.name == 'Brand'
    assert [(m.user_id, m.role, m.status) for m in members.items] == [
        (11, MemberRole.OWNER, MemberStatus.ACTIVE)
    ]


@pytest.mark.asyncio
async def test_get_projects_forwards_filters_and_pagination(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    await project_repo.create_project('Other', 2)
    await member_repo.create_member(
        project.id, 1, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    result = await project_repo.get_projects_for_member(
        user_id=1, name='Brand', pagination=PaginationDTO(limit=10)
    )
    assert result.items[0].id == project.id


@pytest.mark.asyncio
async def test_update_project_requires_active_project_member(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    with pytest.raises(ProjectNotFoundException):
        await update_project(
            project_repo, member_repo, project.id, 2, UpdateProjectDTO('New')
        )


@pytest.mark.asyncio
async def test_update_project_requires_owner_or_director(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 2, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await update_project(
            project_repo, member_repo, project.id, 2, UpdateProjectDTO('New')
        )


@pytest.mark.asyncio
async def test_update_project_success(project_repo, member_repo):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 2, MemberRole.DIRECTOR, MemberStatus.ACTIVE
    )
    updated = await update_project(
        project_repo, member_repo, project.id, 2, UpdateProjectDTO('New')
    )
    assert updated.name == 'New'


@pytest.mark.asyncio
async def test_update_project_raises_if_repository_returns_none(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 1, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    project_repo.update_project = AsyncMock(return_value=None)
    with pytest.raises(ProjectNotFoundException):
        await update_project(
            project_repo, member_repo, project.id, 1, UpdateProjectDTO('New')
        )


@pytest.mark.asyncio
async def test_delete_project_requires_role(project_repo, member_repo):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 2, MemberRole.MEMBER, MemberStatus.ACTIVE
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await delete_project(project_repo, member_repo, project.id, 2)


@pytest.mark.asyncio
async def test_delete_project_success_and_hidden_for_nonmember(
    project_repo, member_repo
):
    project = await project_repo.create_project('Brand', 1)
    await member_repo.create_member(
        project.id, 1, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    await delete_project(project_repo, member_repo, project.id, 1)
    assert await project_repo.get_project(project.id) is None
    with pytest.raises(ProjectNotFoundException):
        await delete_project(project_repo, member_repo, project.id, 1)


@pytest.mark.asyncio
async def test_get_projects_only_returns_member_projects(
    project_repo, member_repo
):
    owned = await project_repo.create_project('Brand', 1)
    await project_repo.create_project('Private', 2)
    await member_repo.create_member(
        owned.id, 1, MemberRole.OWNER, MemberStatus.ACTIVE
    )
    result = await get_projects(project_repo, 1, pagination=PaginationDTO())
    assert [project.id for project in result.items] == [owned.id]
