# ruff: noqa: PLR2004
from http import HTTPStatus

import pytest

from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
from project.entities.asset import AssetStatus
from project.exceptions import (
    AssetNotFoundException,
    InsufficientProjectPermissionException,
    ProjectUserAuthenticationException,
    ProjectUserServiceException,
)


@pytest.mark.asyncio
async def test_list_assets_returns_page_and_passes_filters(
    asset_client, asset_api
):
    response = await asset_client.get(
        '/projects/2/assets?limit=10&type=image&status=active',
        cookies={'jwt': 'token'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'][0]['id'] == 4
    assert response.json()['items'][0]['tags'][0]['id'] == 9
    assert response.json()['limit'] == 10
    assert response.json()['more'] is False
    asset_api[3].get_assets.assert_awaited_once()
    assert asset_api[4].get_current_user.await_count == 1


@pytest.mark.asyncio
async def test_assets_require_authentication(asset_client):
    response = await asset_client.get('/projects/2/assets')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_asset_file_route_redirects_to_signed_url(
    asset_client, asset_api
):
    asset_api[5].get_presigned_url.return_value = 'https://rustfs.test/view'

    response = await asset_client.get(
        '/projects/2/assets/4/file', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers['location'] == 'https://rustfs.test/view'
    asset_api[5].get_presigned_url.assert_awaited_once_with(
        'projects/2/assets/file',
        download_filename='asset-4',
        disposition='inline',
    )


@pytest.mark.asyncio
async def test_asset_download_route_redirects_to_attachment_url(
    asset_client, asset_api
):
    asset_api[5].get_presigned_url.return_value = 'https://rustfs.test/download'

    response = await asset_client.get(
        '/projects/2/assets/4/download', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.TEMPORARY_REDIRECT
    assert response.headers['location'] == 'https://rustfs.test/download'
    asset_api[5].get_presigned_url.assert_awaited_once_with(
        'projects/2/assets/file', download_filename='asset-4'
    )


@pytest.mark.asyncio
async def test_asset_file_route_requires_authentication(
    asset_client, asset_api
):
    response = await asset_client.get('/projects/2/assets/4/file')

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    asset_api[5].get_presigned_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_download_route_maps_missing_asset(asset_client, asset_api):
    asset_api[3].get_asset.return_value = None

    response = await asset_client.get(
        '/projects/2/assets/404/download', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    asset_api[5].get_presigned_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_client_authentication_error_is_translated(
    asset_client, asset_api
):
    asset_api[
        4
    ].get_current_user.side_effect = ProjectUserAuthenticationException()
    response = await asset_client.get(
        '/projects/2/assets', cookies={'jwt': 'expired'}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail'] == 'Invalid or expired user access token'


@pytest.mark.asyncio
async def test_user_client_service_error_is_gateway_error(
    asset_client, asset_api
):
    asset_api[4].get_current_user.side_effect = ProjectUserServiceException()
    response = await asset_client.get(
        '/projects/2/assets', cookies={'jwt': 'token'}
    )
    assert response.status_code == HTTPStatus.BAD_GATEWAY


@pytest.mark.asyncio
async def test_list_assets_rejects_invalid_cursor(asset_client):
    response = await asset_client.get(
        '/projects/2/assets?cursor=bad',
        cookies={'jwt': 'token'},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_list_assets_rejects_invalid_limit(asset_client):
    response = await asset_client.get(
        '/projects/2/assets?limit=0', cookies={'jwt': 'token'}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_create_asset_returns_presigned_upload(asset_client, asset_api):
    response = await asset_client.post(
        '/projects/2/assets',
        cookies={'jwt': 'token'},
        json={
            'type': 'image',
            'name': 'Logo',
            'original_filename': 'logo.png',
            'description': 'cover',
            'content_type': 'image/png',
        },
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['id'] == 4
    assert response.json()['file'] is not None
    assert response.json()['upload_url'] == (
        asset_api[5].generate_presigned_put_url.return_value
    )
    assert response.json()['method'] == 'PUT'
    asset_api[5].generate_presigned_put_url.assert_awaited_once()
    asset_api[3].create_asset.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_asset_maps_domain_error(asset_client, asset_api):
    asset_api[3].create_asset.side_effect = AssetNotFoundException(4)
    response = await asset_client.post(
        '/projects/2/assets',
        cookies={'jwt': 'token'},
        json={
            'type': 'image',
            'name': 'Logo',
            'original_filename': 'logo.png',
        },
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_start_asset_replacement_returns_presigned_upload(
    asset_client, asset_api
):
    response = await asset_client.post(
        '/projects/2/assets/4/uploads',
        cookies={'jwt': 'token'},
        json={
            'original_filename': 'logo.png',
            'content_type': 'image/png',
        },
    )
    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json()['upload_url'] == (
        asset_api[5].generate_presigned_put_url.return_value
    )
    asset_api[3].update_asset.assert_awaited_once_with(
        4, status=AssetStatus.UPLOADING
    )


@pytest.mark.asyncio
async def test_start_asset_replacement_maps_domain_error(
    asset_client, asset_api
):
    asset_api[3].get_asset.side_effect = AssetNotFoundException(404)

    response = await asset_client.post(
        '/projects/2/assets/404/uploads',
        cookies={'jwt': 'token'},
        json={'original_filename': 'logo.png'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    asset_api[5].generate_presigned_put_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_asset_without_file(asset_client, asset_api):
    response = await asset_client.put(
        '/projects/2/assets/4',
        cookies={'jwt': 'token'},
        json={'type': 'photo'},
    )
    assert response.status_code == HTTPStatus.OK
    asset_api[5].save.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_asset_maps_domain_error(asset_client, asset_api):
    asset_api[3].update_asset.side_effect = AssetNotFoundException(4)
    response = await asset_client.put(
        '/projects/2/assets/4',
        cookies={'jwt': 'token'},
        json={'type': 'photo'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_asset_permission_error_is_forbidden(asset_client, asset_api):
    asset_api[
        1
    ].get_project.side_effect = InsufficientProjectPermissionException(
        'asset_read'
    )
    response = await asset_client.get(
        '/projects/2/assets', cookies={'jwt': 'token'}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_asset_not_found_is_404(asset_client, asset_api):
    asset_api[3].update_asset.side_effect = AssetNotFoundException(404)
    response = await asset_client.put(
        '/projects/2/assets/404',
        cookies={'jwt': 'token'},
        json={'type': 'photo'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_asset(asset_client, asset_api):
    response = await asset_client.delete(
        '/projects/2/assets/4', cookies={'jwt': 'token'}
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    asset_api[3].delete_asset.assert_awaited_once_with(4)
    asset_api[5].delete.assert_awaited_once_with('projects/2/assets/file')


@pytest.mark.asyncio
async def test_delete_asset_maps_domain_error(asset_client, asset_api):
    asset_api[3].delete_asset.side_effect = AssetNotFoundException(4)
    response = await asset_client.delete(
        '/projects/2/assets/4', cookies={'jwt': 'token'}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_asset_history_returns_events(asset_client, asset_api):
    now = asset_api[6].created_at
    event = ResourceEventDTO(
        1, 2, 'asset', 4, 1, 'metadata_changed', {'changes': {}}, None, now
    )
    asset_api[7].resource_event_repository.get_events.return_value = CursorPage(
        [event], PaginationDTO(limit=10)
    )
    response = await asset_client.get(
        '/projects/2/assets/4/history?limit=10', cookies={'jwt': 'token'}
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'][0]['event_type'] == 'metadata_changed'
    asset_api[7].resource_event_repository.get_events.assert_awaited_once_with(
        2, 'asset', 4, PaginationDTO(limit=10)
    )


@pytest.mark.asyncio
async def test_asset_history_maps_domain_error(asset_client, asset_api):
    asset_api[
        7
    ].resource_event_repository.get_events.side_effect = AssetNotFoundException(
        404
    )

    response = await asset_client.get(
        '/projects/2/assets/404/history', cookies={'jwt': 'token'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
