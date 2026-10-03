import pytest

from project.dtos.page import PaginationDTO
from project.repositories.project import ProjectRepository


@pytest.mark.asyncio
async def test_create_project_returns_dto(
    project_repo: ProjectRepository,
) -> None:
    owner_id = 11
    dto = await project_repo.create_project('Identity', owner_id=owner_id)

    assert dto.name == 'Identity'
    assert dto.owner_id == owner_id
    assert dto.created_at is not None


@pytest.mark.asyncio
async def test_get_project_returns_none_when_missing(
    project_repo: ProjectRepository,
) -> None:
    dto = await project_repo.get_project(404)

    assert dto is None


@pytest.mark.asyncio
async def test_get_projects_for_member_filters_name_and_paginates(
    project_repo: ProjectRepository, member_repo
) -> None:
    matching = await project_repo.create_project('Brand alpha', owner_id=1)
    excluded = await project_repo.create_project('Other brand', owner_id=2)
    await member_repo.create_member(matching.id, user_id=101, status='active')
    await member_repo.create_member(excluded.id, user_id=101, status='active')

    page = await project_repo.get_projects_for_member(
        101, name='alpha', pagination=PaginationDTO(limit=1)
    )

    assert [item.id for item in page.items] == [matching.id]
    assert page.pagination.cursor is None
    assert page.pagination.more is False


@pytest.mark.asyncio
async def test_project_cursor_returns_older_projects_without_duplicates(
    project_repo: ProjectRepository, member_repo
) -> None:
    projects = [
        await project_repo.create_project(f'Brand {index}', owner_id=index)
        for index in range(1, 4)
    ]
    for project in projects:
        await member_repo.create_member(
            project.id, user_id=202, status='active'
        )

    first_page = await project_repo.get_projects_for_member(
        202, pagination=PaginationDTO(limit=1)
    )
    second_page = await project_repo.get_projects_for_member(
        202,
        pagination=PaginationDTO(limit=1, cursor=first_page.pagination.cursor),
    )

    assert first_page.items[0].id == projects[-1].id
    assert second_page.items[0].id == projects[-2].id
    assert first_page.pagination.more is True


@pytest.mark.asyncio
async def test_update_and_delete_project(
    project_repo: ProjectRepository,
) -> None:
    created = await project_repo.create_project('Old name', owner_id=3)

    updated = await project_repo.update_project(created.id, name='New name')
    deleted = await project_repo.delete_project(created.id)

    assert updated is not None and updated.name == 'New name'
    assert deleted is None
    assert await project_repo.get_project(created.id) is None


@pytest.mark.asyncio
async def test_update_project_returns_none_when_missing(
    project_repo: ProjectRepository,
) -> None:
    result = await project_repo.update_project(404, name='Missing')

    assert result is None


@pytest.mark.asyncio
async def test_delete_project_does_nothing_when_missing(
    project_repo: ProjectRepository,
) -> None:
    result = await project_repo.delete_project(404)

    assert result is None


@pytest.mark.asyncio
async def test_update_project_changes_owner(
    project_repo: ProjectRepository,
) -> None:
    created = await project_repo.create_project('Brand', owner_id=3)
    new_owner_id = 4

    updated = await project_repo.update_project(
        created.id, owner_id=new_owner_id
    )

    assert updated is not None and updated.owner_id == new_owner_id
