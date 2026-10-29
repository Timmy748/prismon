from http import HTTPStatus
from types import SimpleNamespace

import pytest

from project.entities.api_key import ApiKeyProvider
from project.use_cases.api_key import (
    create_member_api_key,
    create_project_api_key,
)

pytest_plugins = ['project.tests.fixtures.api_key_routes']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('post', '/members/me/api-keys'),
        ('get', '/members/me/api-keys'),
        ('post', '/api-keys'),
        ('get', '/api-keys'),
        ('delete', '/api-keys/42'),
    ],
)
async def test_api_key_routes_require_authentication(
    api_key_route_client, api_key_context, method, path
):
    _, project, _, _ = api_key_context
    kwargs = (
        {'json': {'provider': 'openrouter', 'api_key': 'secret-value'}}
        if method == 'post'
        else {}
    )
    response = await api_key_route_client.request(
        method, f'/projects/{project.id}{path}', **kwargs
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('path', 'user'), [('/members/me/api-keys', '2'), ('/api-keys', '1')]
)
async def test_create_api_key_returns_only_hint(
    api_key_route_client, api_key_context, path, user
):
    _, project, _, _ = api_key_context
    response = await api_key_route_client.post(
        f'/projects/{project.id}{path}',
        cookies={'jwt': user},
        json={'provider': 'openrouter', 'api_key': 'secret-value'},
    )
    assert response.status_code == HTTPStatus.CREATED
    assert set(response.json()) == {'id', 'provider', 'api_hint', 'created_at'}
    assert response.json()['api_hint'] == '****alue'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('path', 'user'), [('/members/me/api-keys', '2'), ('/api-keys', '1')]
)
async def test_list_api_keys_returns_only_hints(
    api_key_route_client, api_key_context, key_encryptor, path, user
):
    uow, project, _, _ = api_key_context
    create = create_member_api_key if user == '2' else create_project_api_key
    await create(
        uow,
        project.id,
        int(user),
        ApiKeyProvider.OPENROUTER,
        'secret-value',
        key_encryptor,
    )
    response = await api_key_route_client.get(
        f'/projects/{project.id}{path}', cookies={'jwt': user}
    )
    assert response.status_code == HTTPStatus.OK
    assert len(response.json()['items']) == 1
    assert set(response.json()['items'][0]) == {
        'id',
        'provider',
        'api_hint',
        'created_at',
    }


@pytest.mark.asyncio
async def test_delete_api_key_returns_no_content(
    api_key_route_client, api_key_context, key_encryptor
):
    uow, project, _, _ = api_key_context
    key = await create_member_api_key(
        uow,
        project.id,
        2,
        ApiKeyProvider.OPENROUTER,
        'secret-value',
        key_encryptor,
    )
    response = await api_key_route_client.delete(
        f'/projects/{project.id}/api-keys/{key.id}', cookies={'jwt': '2'}
    )
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''
    assert await uow.api_key_repository.get_api_key(key.id) is None


@pytest.mark.asyncio
async def test_nonowner_cannot_create_project_key(
    api_key_route_client, api_key_context
):
    _, project, _, _ = api_key_context
    response = await api_key_route_client.post(
        f'/projects/{project.id}/api-keys',
        cookies={'jwt': '2'},
        json={'provider': 'openrouter', 'api_key': 'secret-value'},
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['/members/me/api-keys', '/api-keys'])
async def test_invalid_provider_is_rejected(
    api_key_route_client, api_key_context, path
):
    _, project, _, _ = api_key_context
    response = await api_key_route_client.post(
        f'/projects/{project.id}{path}',
        cookies={'jwt': '1'},
        json={'provider': 'invalid', 'api_key': 'secret-value'},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('post', '/members/me/api-keys'),
        ('get', '/members/me/api-keys'),
        ('post', '/api-keys'),
        ('get', '/api-keys'),
        ('delete', '/api-keys/42'),
    ],
)
async def test_nonmember_cannot_access_api_keys(
    api_key_route_client, api_key_context, method, path
):
    _, project, _, _ = api_key_context
    kwargs = (
        {'json': {'provider': 'openrouter', 'api_key': 'secret-value'}}
        if method == 'post'
        else {}
    )
    response = await api_key_route_client.request(
        method, f'/projects/{project.id}{path}', cookies={'jwt': '99'}, **kwargs
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['/members/me/api-keys', '/api-keys'])
async def test_listing_validates_limit_and_cursor(
    api_key_route_client, api_key_context, path
):
    _, project, _, _ = api_key_context
    response = await api_key_route_client.get(
        f'/projects/{project.id}{path}?cursor=bad', cookies={'jwt': '1'}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.asyncio
@pytest.mark.parametrize('limit', [0, 101])
async def test_listing_rejects_out_of_range_limit(
    api_key_route_client, api_key_context, limit
):
    _, project, _, _ = api_key_context
    response = await api_key_route_client.get(
        f'/projects/{project.id}/api-keys?limit={limit}', cookies={'jwt': '1'}
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['/members/me/api-keys', '/api-keys'])
async def test_listing_returns_cursor_to_next_page(
    api_key_route_client, api_key_context, key_encryptor, path
):
    uow, project, _, _ = api_key_context
    create = (
        create_member_api_key
        if path.startswith('/members')
        else create_project_api_key
    )
    for secret in ('first', 'second'):
        await create(
            uow, project.id, 1, ApiKeyProvider.OPENROUTER, secret, key_encryptor
        )
    response = await api_key_route_client.get(
        f'/projects/{project.id}{path}?limit=1', cookies={'jwt': '1'}
    )
    page = response.json()
    next_response = await api_key_route_client.get(
        f'/projects/{project.id}{path}',
        params={'limit': 1, 'cursor': page['cursor']},
        cookies={'jwt': '1'},
    )
    assert page['more'] is True
    assert next_response.json()['more'] is False
    assert page['items'][0]['id'] != next_response.json()['items'][0]['id']


@pytest.mark.asyncio
@pytest.mark.parametrize('scope', ['member', 'project'])
async def test_listing_endpoint_directly_returns_page(
    api_key_context, key_encryptor, api_key_direct_router, scope
):
    uow, project, _, _ = api_key_context
    create = (
        create_member_api_key if scope == 'member' else create_project_api_key
    )
    key = await create(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'secret', key_encryptor
    )

    path = (
        '/projects/{project_id}/members/me/api-keys'
        if scope == 'member'
        else '/projects/{project_id}/api-keys'
    )
    endpoint = next(
        route.endpoint
        for route in api_key_direct_router.routes
        if route.path == path and 'GET' in route.methods
    )
    result = await endpoint(
        SimpleNamespace(cookies={'jwt': 'token'}), project.id, 1, None
    )
    assert [item.id for item in result.items] == [key.id]


@pytest.mark.asyncio
async def test_delete_endpoint_directly_removes_key(
    api_key_context, key_encryptor, api_key_direct_router
):
    uow, project, _, _ = api_key_context
    key = await create_member_api_key(
        uow, project.id, 1, ApiKeyProvider.OPENROUTER, 'secret', key_encryptor
    )

    endpoint = next(
        route.endpoint
        for route in api_key_direct_router.routes
        if 'DELETE' in route.methods
    )
    result = await endpoint(
        SimpleNamespace(cookies={'jwt': 'token'}), project.id, key.id
    )
    assert result is None
    assert await uow.api_key_repository.get_api_key(key.id) is None
