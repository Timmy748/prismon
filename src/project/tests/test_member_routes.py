# ruff: noqa: PLR2004
import pytest

from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    ProjectNotFoundException,
    ProjectUserAuthenticationException,
)
from project.tests.fixtures.members import make_member


def owner_member():
    return make_member(member_id=10, user_id=7, role=MemberRole.OWNER)


def test_member_routes_are_registered(member_route_app):
    paths = member_route_app.openapi()['paths']
    assert '/projects/{project_id}/members' in paths
    assert '/projects/{project_id}/members/accept' in paths
    assert '/projects/{project_id}/members/refuse' in paths
    assert '/projects/{project_id}/members/{member_id}' in paths


@pytest.mark.asyncio
async def test_members_list_requires_authentication(
    member_route_client, member_route_dependencies
):
    response = await member_route_client.get('/projects/3/members')
    assert response.status_code == 401
    member_route_dependencies[2].get_current_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_members_list_returns_page(
    member_route_client, member_route_dependencies
):
    project_repo, member_repo, _ = member_route_dependencies
    project_repo.get_project.return_value = object()
    member_repo.get_members.side_effect = [
        CursorPage([owner_member()], PaginationDTO()),
        CursorPage([make_member()], PaginationDTO(limit=10)),
    ]
    response = await member_route_client.get(
        '/projects/3/members?limit=10',
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == 200
    assert response.json()['limit'] == 10
    assert response.json()['more'] is False
    assert response.json()['cursor'] is None
    assert response.json()['items'][0]['user_id'] == 19


@pytest.mark.asyncio
async def test_invalid_cursor_is_bad_request(member_route_client):
    response = await member_route_client.get(
        '/projects/3/members?cursor=bad',
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_user_client_authentication_error_is_mapped(
    member_route_client, member_route_dependencies
):
    member_route_dependencies[
        2
    ].get_current_user.side_effect = ProjectUserAuthenticationException()
    response = await member_route_client.get(
        '/projects/3/members', headers={'Authorization': 'Bearer invalid'}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_project_error_is_mapped(
    member_route_client, member_route_dependencies
):
    member_route_dependencies[
        1
    ].get_members.side_effect = ProjectNotFoundException(3)
    response = await member_route_client.get(
        '/projects/3/members', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_invite_uses_user_id_contract(
    member_route_client, member_route_dependencies
):
    _, repo, _ = member_route_dependencies
    repo.get_members.side_effect = [
        CursorPage([owner_member()], PaginationDTO()),
        CursorPage([], PaginationDTO()),
    ]
    repo.create_member.return_value = make_member(
        user_id=19, status=MemberStatus.PENDING
    )
    response = await member_route_client.post(
        '/projects/3/members',
        json={'user_id': 19},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == 201
    assert response.json()['user_id'] == 19


@pytest.mark.asyncio
async def test_invite_permission_error(
    member_route_client, member_route_dependencies
):
    member_route_dependencies[1].get_members.return_value = CursorPage(
        [make_member(user_id=7, role=MemberRole.MEMBER)], PaginationDTO()
    )
    response = await member_route_client.post(
        '/projects/3/members',
        json={'user_id': 19},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_role_change(member_route_client, member_route_dependencies):
    project_repo, repo, _ = member_route_dependencies
    project_repo.get_project.return_value = object()
    repo.get_members.return_value = CursorPage(
        [owner_member()], PaginationDTO()
    )
    repo.get_member.return_value = make_member()
    repo.update_member.return_value = make_member(role=MemberRole.DIRECTOR)
    response = await member_route_client.patch(
        '/projects/3/members/11',
        json={'new_role': 'director'},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == 200
    assert response.json()['role'] == 'director'


@pytest.mark.asyncio
async def test_accept_invitation(
    member_route_client, member_route_dependencies
):
    project_repo, repo, _ = member_route_dependencies
    project_repo.get_project.return_value = object()
    repo.get_members.return_value = CursorPage(
        [make_member(user_id=7, status=MemberStatus.PENDING)], PaginationDTO()
    )
    repo.update_member.return_value = make_member(user_id=7)
    response = await member_route_client.patch(
        '/projects/3/members/accept', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 200
    assert response.json()['status'] == 'active'


@pytest.mark.asyncio
async def test_refuse_invitation(
    member_route_client, member_route_dependencies
):
    project_repo, repo, _ = member_route_dependencies
    project_repo.get_project.return_value = object()
    repo.get_members.return_value = CursorPage(
        [make_member(user_id=7, status=MemberStatus.PENDING)], PaginationDTO()
    )
    response = await member_route_client.patch(
        '/projects/3/members/refuse', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 200
    repo.delete_member.assert_awaited_once_with(11)


@pytest.mark.asyncio
async def test_remove_member(member_route_client, member_route_dependencies):
    project_repo, repo, _ = member_route_dependencies
    project_repo.get_project.return_value = object()
    repo.get_members.return_value = CursorPage(
        [owner_member()], PaginationDTO()
    )
    repo.get_member.return_value = make_member()
    response = await member_route_client.delete(
        '/projects/3/members/11', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_invitation_domain_error_is_mapped(
    member_route_client, member_route_dependencies
):
    member_route_dependencies[
        0
    ].get_project.side_effect = ProjectNotFoundException(3)
    response = await member_route_client.patch(
        '/projects/3/members/accept', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_role_change_domain_error_is_mapped(
    member_route_client, member_route_dependencies
):
    member_route_dependencies[
        0
    ].get_project.side_effect = ProjectNotFoundException(3)
    response = await member_route_client.patch(
        '/projects/3/members/11',
        json={'new_role': 'director'},
        headers={'Authorization': 'Bearer valid'},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_remove_member_domain_error_is_mapped(
    member_route_client, member_route_dependencies
):
    member_route_dependencies[
        0
    ].get_project.side_effect = ProjectNotFoundException(3)
    response = await member_route_client.delete(
        '/projects/3/members/11', headers={'Authorization': 'Bearer valid'}
    )
    assert response.status_code == 404
