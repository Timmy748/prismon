# ruff: noqa: PLR2004
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
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
async def test_document_file_route_redirects_to_signed_url(
    document_client, document_api
):
    document_api[5].get_presigned_url.return_value = 'https://rustfs.test/view'

    response = await document_client.get(
        '/projects/2/documents/4/file', cookies={'jwt': 'token'}
    )

    assert response.status_code == 307
    assert response.headers['location'] == 'https://rustfs.test/view'
    document_api[5].get_presigned_url.assert_awaited_once_with(
        'projects/2/documents/file',
        download_filename='Brief',
        disposition='inline',
    )


@pytest.mark.asyncio
async def test_document_download_route_redirects_to_attachment_url(
    document_client, document_api
):
    document_api[
        5
    ].get_presigned_url.return_value = 'https://rustfs.test/download'

    response = await document_client.get(
        '/projects/2/documents/4/download', cookies={'jwt': 'token'}
    )

    assert response.status_code == 307
    assert response.headers['location'] == 'https://rustfs.test/download'
    document_api[5].get_presigned_url.assert_awaited_once_with(
        'projects/2/documents/file', download_filename='Brief'
    )


@pytest.mark.asyncio
async def test_document_file_route_requires_authentication(
    document_client, document_api
):
    response = await document_client.get('/projects/2/documents/4/file')

    assert response.status_code == 401
    document_api[5].get_presigned_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_download_route_maps_missing_document(
    document_client, document_api
):
    document_api[3].get_document.return_value = None

    response = await document_client.get(
        '/projects/2/documents/404/download', cookies={'jwt': 'token'}
    )

    assert response.status_code == 404
    document_api[5].get_presigned_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_client_authentication_error_is_mapped(
    document_client, document_api
):
    document_api[
        4
    ].get_current_user.side_effect = ProjectUserAuthenticationException()
    response = await document_client.get(
        '/projects/2/documents', cookies={'jwt': 'invalid'}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_documents_returns_page(document_client):
    response = await document_client.get(
        '/projects/2/documents?limit=10',
        cookies={'jwt': 'token'},
    )
    assert response.status_code == 200
    assert response.json()['items'][0]['id'] == 4
    assert response.json()['items'][0]['tags'][0]['id'] == 9
    assert response.json()['limit'] == 10
    assert response.json()['more'] is False
    assert response.json()['cursor'] is None


@pytest.mark.asyncio
async def test_list_forwards_cursor_and_filters(document_client, document_api):
    cursor = (datetime(2026, 1, 2, tzinfo=UTC), 12)
    response = await document_client.get(
        f'/projects/2/documents?cursor={encode_cursor(cursor)}&limit=10'
        '&name=Brief&status=published',
        cookies={'jwt': 'token'},
    )
    assert response.status_code == 200
    call = document_api[3].get_documents.await_args
    assert call.args[1] == PaginationDTO(cursor=cursor, limit=10)
    assert call.args[2:] == ('Brief', DocumentStatus.PUBLISHED)


@pytest.mark.asyncio
async def test_invalid_cursor_is_bad_request(document_client, document_api):
    response = await document_client.get(
        '/projects/2/documents?cursor=bad',
        cookies={'jwt': 'token'},
    )
    assert response.status_code == 400
    document_api[3].get_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_document_returns_signed_upload_url(
    document_client, document_api
):
    response = await document_client.post(
        '/projects/2/documents',
        cookies={'jwt': 'token'},
        json={
            'name': 'Brief',
            'original_filename': 'texto.md',
            'description': 'Project brief',
        },
    )
    assert response.status_code == 201
    assert response.json()['id'] == 4
    assert response.json()['status'] == 'uploading'
    assert response.json()['file'] is None
    assert response.json()['upload_url'] == 'https://rustfs.test/upload'
    assert response.json()['required_headers'] == {
        'Content-Type': 'application/octet-stream'
    }
    document_api[5].generate_presigned_put_url.assert_awaited_once()
    document_api[3].create_document.assert_awaited_once()
    assert (
        document_api[3].create_document.await_args.kwargs[
            'created_by_member_id'
        ]
        == 1
    )


@pytest.mark.asyncio
async def test_update_document_changes_metadata_only(
    document_client, document_api
):
    response = await document_client.put(
        '/projects/2/documents/4',
        cookies={'jwt': 'token'},
        json={'name': 'Updated'},
    )
    assert response.status_code == 200
    document_api[3].update_document.assert_awaited_once()
    document_api[5].save.assert_not_awaited()
    document_api[5].delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_document_metadata_without_file(
    document_client, document_api
):
    response = await document_client.put(
        '/projects/2/documents/4',
        cookies={'jwt': 'token'},
        json={'name': 'Updated'},
    )
    assert response.status_code == 200
    document_api[5].save.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_document_removes_metadata_and_file(
    document_client, document_api
):
    response = await document_client.delete(
        '/projects/2/documents/4', cookies={'jwt': 'token'}
    )
    assert response.status_code == 204
    document_api[3].delete_document.assert_awaited_once_with(4)
    document_api[5].delete.assert_awaited_once_with(document_api[6].file)
    calls = document_api[
        7
    ].resource_event_repository.create_event.await_args_list
    assert any(call.args[4] == 'resource_deleted' for call in calls)


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
        cookies={'jwt': 'token'},
        json={'name': 'Brief', 'original_filename': 'texto.md'},
    )
    assert response.status_code == 403
    assert 'permission' in response.json()['detail'].lower()
    document_api[5].generate_presigned_put_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_document_is_not_found(document_client, document_api):
    document_api[3].get_document.return_value = None
    response = await document_client.delete(
        '/projects/2/documents/999', cookies={'jwt': 'token'}
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
        cookies={'jwt': 'token'},
        json={'name': 'Missing'},
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
        '/projects/2/documents', cookies={'jwt': 'token'}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_replace_document_returns_accepted_signed_upload(
    document_client, document_api
):
    document_api[3].update_document.return_value = replace(
        document_api[6], status=DocumentStatus.UPLOADING
    )
    response = await document_client.post(
        '/projects/2/documents/4/uploads',
        cookies={'jwt': 'token'},
        json={
            'original_filename': 'brief.pdf',
            'content_type': 'application/pdf',
        },
    )

    assert response.status_code == 202
    assert response.json()['status'] == 'uploading'
    document_api[5].generate_presigned_put_url.assert_awaited_once()
    document_api[3].update_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_replace_missing_document_maps_not_found(
    document_client, document_api
):
    document_api[3].get_document.return_value = None

    response = await document_client.post(
        '/projects/2/documents/404/uploads',
        cookies={'jwt': 'token'},
        json={'original_filename': 'brief.pdf'},
    )

    assert response.status_code == 404
    document_api[5].generate_presigned_put_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_history_returns_event_page(
    document_client, document_api
):
    now = datetime.now(UTC)
    event = ResourceEventDTO(
        3,
        2,
        'document',
        4,
        1,
        'metadata_changed',
        {'name': 'Brief'},
        None,
        now,
    )
    document_api[
        7
    ].resource_event_repository.get_events.return_value = CursorPage(
        [event], PaginationDTO(limit=25)
    )

    response = await document_client.get(
        '/projects/2/documents/4/history?limit=25', cookies={'jwt': 'token'}
    )

    assert response.status_code == 200
    assert response.json()['items'][0]['event_type'] == 'metadata_changed'
    assert response.json()['items'][0]['author_member_id'] == 1
    document_api[7].resource_event_repository.get_events.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_history_nonmember_is_not_found(
    document_client, document_api
):
    document_api[2].get_members.return_value = CursorPage([], PaginationDTO())

    response = await document_client.get(
        '/projects/2/documents/4/history', cookies={'jwt': 'token'}
    )

    assert response.status_code == 404
    document_api[7].resource_event_repository.get_events.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_history_is_available_after_document_deletion(
    document_client, document_api
):
    now = datetime.now(UTC)
    event = ResourceEventDTO(
        4, 2, 'document', 4, 1, 'resource_deleted', {}, None, now
    )
    document_api[
        7
    ].resource_event_repository.get_events.return_value = CursorPage(
        [event], PaginationDTO(limit=50)
    )
    deleted = await document_client.delete(
        '/projects/2/documents/4', cookies={'jwt': 'token'}
    )

    history = await document_client.get(
        '/projects/2/documents/4/history', cookies={'jwt': 'token'}
    )

    assert deleted.status_code == 204
    assert history.status_code == 200
    assert history.json()['items'][0]['event_type'] == 'resource_deleted'
