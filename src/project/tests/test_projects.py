# ruff: noqa: PLR2004
from datetime import datetime, timezone
from http import HTTPStatus

import pytest

from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    ProjectNotFoundException,
    ProjectUserAuthenticationException,
)


@pytest.mark.asyncio
async def test_projects_requires_authentication(project_http_client):
    response = await project_http_client.get('/projects')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_list_projects_returns_cursor_page(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
    sample_project_dto,
):
    project_repo = project_route_dependencies[0]
    project_repo.get_projects_for_member.return_value = CursorPage(
        [sample_project_dto], PaginationDTO(limit=5, more=False)
    )
    response = await project_http_client.get(
        '/projects?name=Brand&limit=5',
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == HTTPStatus.OK
    result = response.json()
    project = result['items'][0]
    assert project['id'] == 12
    assert project['name'] == 'Brand'
    assert project['owner_id'] == 7
    assert (
        datetime.fromisoformat(project['created_at'])
        == sample_project_dto.created_at
    )
    assert (
        datetime.fromisoformat(project['updated_at'])
        == sample_project_dto.updated_at
    )
    assert result['limit'] == 5
    assert result['more'] is False
    assert result['cursor'] is None
    project_repo.get_projects_for_member.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_projects_rejects_invalid_cursor(
    project_http_client,
    authenticated_project_user,
):
    response = await project_http_client.get(
        '/projects?cursor=bad', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_create_project_registers_authenticated_owner(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
    sample_project_dto,
):
    project_repo, member_repo, _ = project_route_dependencies
    project_repo.create_project.return_value = sample_project_dto
    response = await project_http_client.post(
        '/projects',
        json={'name': 'Brand'},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['owner_id'] == 7
    project_repo.create_project.assert_awaited_once_with('Brand', 7)
    member_repo.create_member.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_project_maps_domain_error(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
):
    project_route_dependencies[
        0
    ].create_project.side_effect = ProjectNotFoundException(42)
    response = await project_http_client.post(
        '/projects',
        json={'name': 'Brand'},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'Project 42 not found'


@pytest.mark.asyncio
async def test_update_project_maps_permission_error(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
    sample_project_dto,
):
    project_repo, member_repo, _ = project_route_dependencies
    project_repo.get_project.return_value = sample_project_dto
    now = datetime.now(timezone.utc)
    member_repo.get_members.return_value = CursorPage(
        [
            MemberDTO(
                1, 12, MemberRole.COLLABORATOR, MemberStatus.ACTIVE, 7, now, now
            )
        ],
        PaginationDTO(),
    )
    response = await project_http_client.put(
        '/projects/12',
        json={'name': 'Changed'},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert 'detail' in response.json()


@pytest.mark.asyncio
async def test_delete_project_returns_no_content(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
    sample_project_dto,
):
    project_repo, member_repo, _ = project_route_dependencies
    project_repo.get_project.return_value = sample_project_dto
    now = datetime.now(timezone.utc)
    member_repo.get_members.return_value = CursorPage(
        [MemberDTO(1, 12, MemberRole.OWNER, MemberStatus.ACTIVE, 7, now, now)],
        PaginationDTO(),
    )
    response = await project_http_client.delete(
        '/projects/12', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == HTTPStatus.NO_CONTENT


@pytest.mark.asyncio
async def test_delete_project_maps_domain_error(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
):
    project_route_dependencies[0].get_project.return_value = None
    response = await project_http_client.delete(
        '/projects/42', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'Project 42 not found'


@pytest.mark.asyncio
async def test_client_authentication_error_is_project_error(
    project_http_client,
    project_route_dependencies,
):
    project_route_dependencies[
        2
    ].get_current_user.side_effect = ProjectUserAuthenticationException()
    response = await project_http_client.get(
        '/projects', headers={'Authorization': 'Bearer invalid'}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_project_domain_errors_are_handled(
    project_http_client,
    project_route_dependencies,
    authenticated_project_user,
):
    project_route_dependencies[
        0
    ].get_projects_for_member.side_effect = ProjectNotFoundException(42)
    response = await project_http_client.get(
        '/projects', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()['detail'] == 'Project 42 not found'
