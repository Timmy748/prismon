from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from main import app


async def request(
    identity_route_app: FastAPI, method: str, path: str, **kwargs
):
    async with AsyncClient(
        transport=ASGITransport(app=identity_route_app),
        base_url='http://test',
    ) as client:
        return await client.request(method, path, **kwargs)


def test_app_includes_identity_routers():
    paths = app.openapi()['paths']

    assert '/users' in paths
    assert '/login' in paths
    assert '/refresh-token' in paths


@pytest.mark.asyncio
async def test_create_user_route_calls_use_case_dependencies(
    identity_route_app,
    route_user,
    mock_user_repo,
    mock_password_hasher,
):
    mock_user_repo.get_user.return_value = None
    mock_user_repo.create_user.return_value = route_user
    mock_password_hasher.hash.return_value = 'secret-hash'

    response = await request(
        identity_route_app,
        'POST',
        '/users',
        json={
            'username': 'ana',
            'email': 'ana@example.com',
            'password_hash': 'secret',
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()['id'] == route_user.id
    assert 'password_hash' not in response.json()
    mock_password_hasher.hash.assert_called_once_with('secret')


@pytest.mark.asyncio
async def test_get_user_route_returns_404_when_missing(
    identity_route_app, mock_user_repo
):
    mock_user_repo.get_user_by_id.return_value = None

    response = await request(identity_route_app, 'GET', '/users/42')

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_login_route_returns_tokens(
    identity_route_app,
    route_user,
    mock_user_repo,
    mock_password_hasher,
    mock_token_provider,
):
    mock_user_repo.get_user.return_value = route_user
    mock_password_hasher.verify.return_value = True
    mock_token_provider.generate_access_token.return_value = 'access'
    mock_token_provider.generate_refresh_token_hash.return_value = (
        'hashed-refresh'
    )

    response = await request(
        identity_route_app,
        'POST',
        '/login',
        json={'email': 'ana@example.com', 'password': 'secret'},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()['access_token'] == 'access'
    assert response.json()['refresh_token']


@pytest.mark.asyncio
async def test_authenticated_user_route_rejects_missing_token(
    identity_route_app,
):
    response = await request(
        identity_route_app,
        'PUT',
        '/users',
        json={'username': 'nova'},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
