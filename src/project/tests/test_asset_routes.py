# ruff: noqa: PLR2004
from http import HTTPStatus

import pytest

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
        headers={'Authorization': 'Bearer token'},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()['items'][0]['id'] == 4
    assert response.json()['limit'] == 10
    assert response.json()['more'] is False
    asset_api[3].get_assets.assert_awaited_once()
    assert asset_api[4].get_current_user.await_count == 1


@pytest.mark.asyncio
async def test_assets_require_authentication(asset_client):
    response = await asset_client.get('/projects/2/assets')
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_user_client_authentication_error_is_translated(
    asset_client, asset_api
):
    asset_api[
        4
    ].get_current_user.side_effect = ProjectUserAuthenticationException()
    response = await asset_client.get(
        '/projects/2/assets', headers={'Authorization': 'Bearer expired'}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()['detail'] == 'Invalid or expired user access token'


@pytest.mark.asyncio
async def test_user_client_service_error_is_gateway_error(
    asset_client, asset_api
):
    asset_api[4].get_current_user.side_effect = ProjectUserServiceException()
    response = await asset_client.get(
        '/projects/2/assets', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == HTTPStatus.BAD_GATEWAY


@pytest.mark.asyncio
async def test_list_assets_rejects_invalid_cursor(asset_client):
    response = await asset_client.get(
        '/projects/2/assets?cursor=bad',
        headers={'Authorization': 'Bearer token'},
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
async def test_list_assets_rejects_invalid_limit(asset_client):
    response = await asset_client.get(
        '/projects/2/assets?limit=0', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_upload_asset_multipart(asset_client, asset_api):
    response = await asset_client.post(
        '/projects/2/assets',
        headers={'Authorization': 'Bearer token'},
        data={'type': 'image', 'description': 'cover'},
        files={'file': ('cover.png', b'contents', 'image/png')},
    )
    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['id'] == 4
    asset_api[5].save.assert_called_once()


@pytest.mark.asyncio
async def test_upload_asset_maps_domain_error(asset_client, asset_api):
    asset_api[3].create_asset.side_effect = AssetNotFoundException(4)
    response = await asset_client.post(
        '/projects/2/assets',
        headers={'Authorization': 'Bearer token'},
        data={'type': 'image'},
        files={'file': ('cover.png', b'contents', 'image/png')},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_update_asset_can_replace_file(asset_client, asset_api):
    response = await asset_client.put(
        '/projects/2/assets/4',
        headers={'Authorization': 'Bearer token'},
        data={'type': 'photo'},
        files={'file': ('new.png', b'new contents', 'image/png')},
    )
    assert response.status_code == HTTPStatus.OK
    asset_api[3].update_asset.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_asset_without_file(asset_client, asset_api):
    response = await asset_client.put(
        '/projects/2/assets/4',
        headers={'Authorization': 'Bearer token'},
        data={'type': 'photo'},
    )
    assert response.status_code == HTTPStatus.OK
    asset_api[5].save.assert_not_called()


@pytest.mark.asyncio
async def test_update_asset_maps_domain_error(asset_client, asset_api):
    asset_api[3].update_asset.side_effect = AssetNotFoundException(4)
    response = await asset_client.put(
        '/projects/2/assets/4',
        headers={'Authorization': 'Bearer token'},
        data={'type': 'photo'},
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
        '/projects/2/assets', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_asset_not_found_is_404(asset_client, asset_api):
    asset_api[3].update_asset.side_effect = AssetNotFoundException(404)
    response = await asset_client.put(
        '/projects/2/assets/404',
        headers={'Authorization': 'Bearer token'},
        data={'type': 'photo'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_delete_asset(asset_client, asset_api):
    response = await asset_client.delete(
        '/projects/2/assets/4', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    asset_api[3].delete_asset.assert_awaited_once_with(4)
    asset_api[5].delete.assert_called_once_with('projects/2/assets/file')


@pytest.mark.asyncio
async def test_delete_asset_maps_domain_error(asset_client, asset_api):
    asset_api[3].delete_asset.side_effect = AssetNotFoundException(4)
    response = await asset_client.delete(
        '/projects/2/assets/4', headers={'Authorization': 'Bearer token'}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
