# ruff: noqa: PLR2004
from datetime import UTC, datetime

import pytest

from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    InsufficientProjectPermissionException,
    ProjectUserAuthenticationException,
)
from project.utils.pagination import encode_cursor


def test_document_routes_are_registered(document_api):
    paths = document_api[0].openapi()['paths']
    assert '/projects/{project_id}/documents' in paths
    assert '/projects/{project_id}/documents/{document_id}' in paths


@pytest.mark.asyncio
async def test_documents_require_authentication(document_client, document_api):
    response = await document_client.get('/projects/2/documents')
    assert response.status_code == 401
    document_api[4].get_current_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_client_authentication_error_is_mapped(
    document_client, document_api
):
    document_api[
        4
    ].get_current_user.side_effect = ProjectUserAuthenticationException()
    response = await document_client.get(
        '/projects/2/documents', headers={'Authorization': 'Bearer invalid'}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_documents_returns_page(document_client):
    response = await document_client.get(
        '/projects/2/documents?limit=10',
        headers={'Authorization': 'Bearer token'},
    )
    assert response.status_code == 200
    assert response.json()['items'][0]['id'] == 4
    assert response.json()['limit'] == 10
    assert response.json()['more'] is False
    assert response.json()['cursor'] is None


@pytest.mark.asyncio
async def test_list_forwards_cursor_and_filters(document_client, document_api):
    cursor = (datetime(2026, 1, 2, tzinfo=UTC), 12)
    response = await document_client.get(
        f'/projects/2/documents?cursor={encode_cursor(cursor)}&limit=10'
        '&name=Brief&status=published',
        headers={'Authorization': 'Bearer token'},
    )
    assert response.status_code == 200
    call = document_api[3].get_documents.await_args
    assert call.args[1] == PaginationDTO(cursor=cursor, limit=10)
    assert call.args[2:] == ('Brief', DocumentStatus.PUBLISHED)


@pytest.mark.asyncio
async def test_invalid_cursor_is_bad_request(document_client, document_api):
    response = await document_client.get(
        '/projects/2/documents?cursor=bad',
        headers={'Authorization': 'Bearer token'},
    )
    assert response.status_code == 400
    document_api[3].get_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_document_multipart(document_client, document_api):
    response = await document_client.post(
        '/projects/2/documents',
        headers={'Authorization': 'Bearer token'},
        data={'name': 'Brief', 'description': 'Project brief'},
        files={'file': ('brief.pdf', b'contents', 'application/pdf')},
    )
    assert response.status_code == 201
    assert response.json()['id'] == 4
    document_api[5].save.assert_called_once()


@pytest.mark.asyncio
async def test_update_document_replaces_file(document_client, document_api):
    response = await document_client.put(
        '/projects/2/documents/4',
        headers={'Authorization': 'Bearer token'},
        data={'name': 'Updated'},
        files={'file': ('new.pdf', b'new contents', 'application/pdf')},
    )
    assert response.status_code == 200
    document_api[3].update_document.assert_awaited_once()
    document_api[5].delete.assert_called_once_with(document_api[6].file)


@pytest.mark.asyncio
async def test_update_document_metadata_without_file(
    document_client, document_api
):
    response = await document_client.put(
        '/projects/2/documents/4',
        headers={'Authorization': 'Bearer token'},
        data={'name': 'Updated'},
    )
    assert response.status_code == 200
    document_api[5].save.assert_not_called()


@pytest.mark.asyncio
async def test_delete_document_removes_metadata_and_file(
    document_client, document_api
):
    response = await document_client.delete(
        '/projects/2/documents/4', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == 204
    document_api[3].delete_document.assert_awaited_once_with(4)
    document_api[5].delete.assert_called_once_with(document_api[6].file)


@pytest.mark.asyncio
async def test_document_permission_denial_is_forbidden(
    document_client, document_api
):
    now = document_api[6].created_at
    document_api[2].get_members.return_value = CursorPage(
        [
            MemberDTO(
                1,
                2,
                MemberRole.COLLABORATOR,
                MemberStatus.ACTIVE,
                7,
                now,
                now,
            )
        ],
        PaginationDTO(limit=100),
    )
    response = await document_client.post(
        '/projects/2/documents',
        headers={'Authorization': 'Bearer token'},
        data={'name': 'Brief'},
        files={'file': ('brief.pdf', b'contents', 'application/pdf')},
    )
    assert response.status_code == 403
    assert 'permission' in response.json()['detail'].lower()


@pytest.mark.asyncio
async def test_missing_document_is_not_found(document_client, document_api):
    document_api[3].get_document.return_value = None
    response = await document_client.delete(
        '/projects/2/documents/999', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == 404
    document_api[3].delete_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_missing_document_is_not_found(
    document_client, document_api
):
    document_api[3].get_document.return_value = None
    response = await document_client.put(
        '/projects/2/documents/999',
        headers={'Authorization': 'Bearer token'},
        data={'name': 'Missing'},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_exception_maps_to_forbidden(
    document_client, document_api
):
    document_api[
        2
    ].get_members.side_effect = InsufficientProjectPermissionException(
        'document:read'
    )
    response = await document_client.get(
        '/projects/2/documents', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == 403
