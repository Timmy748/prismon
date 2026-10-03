from datetime import datetime, timezone
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from identity.dtos.user import UserDTO
from identity.exceptions import UserAlreadyExistsException


@pytest.mark.asyncio
async def test_post_user_success(
    user_client: AsyncClient,
    mock_user_repo,
    mock_password_hasher,
):
    now = datetime.now(timezone.utc)
    mock_user = UserDTO(
        id=1,
        username='ana',
        email='ana@example.com',
        password_hash='hashed_password',
        created_at=now,
        updated_at=now,
    )
    mock_password_hasher.hash.return_value = 'hashed_password'
    mock_user_repo.get_user.return_value = None
    mock_user_repo.create_user.return_value = mock_user

    response = await user_client.post(
        '/users',
        json={
            'username': 'ana',
            'email': 'ana@example.com',
            'password_hash': 'plain_password_123',
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['id'] == 1
    assert data['username'] == 'ana'
    assert data['email'] == 'ana@example.com'


@pytest.mark.asyncio
async def test_post_user_identity_exception_handled(
    user_client: AsyncClient,
    mock_user_repo,
    mock_password_hasher,
):

    mock_password_hasher.hash.return_value = 'hashed_password'
    mock_user_repo.create_user.side_effect = UserAlreadyExistsException(
        field='email'
    )

    response = await user_client.post(
        '/users',
        json={
            'username': 'ana',
            'email': 'ana@example.com',
            'password_hash': 'plain_password_123',
        },
    )

    assert response.status_code != HTTPStatus.CREATED


@pytest.mark.asyncio
async def test_get_user_success(
    user_client: AsyncClient,
    mock_user_repo,
):
    now = datetime.now(timezone.utc)
    mock_user = UserDTO(
        id=1,
        username='ana',
        email='ana@example.com',
        password_hash='hashed_password',
        created_at=now,
        updated_at=now,
    )
    mock_user_repo.get_user_by_id.return_value = mock_user

    response = await user_client.get('/users/1')

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['id'] == 1
    assert data['username'] == 'ana'


@pytest.mark.asyncio
async def test_get_user_not_found_returns_error_handled(
    user_client: AsyncClient,
    mock_user_repo,
):
    mock_user_repo.get_user_by_id.return_value = None

    response = await user_client.get('/users/999')

    assert response.status_code != HTTPStatus.OK


@pytest.mark.asyncio
async def test_put_user_success(
    user_client: AsyncClient,
    mock_user_repo,
    mock_token_provider,
):
    now = datetime.now(timezone.utc)
    mock_user = UserDTO(
        id=1,
        username='ana_updated',
        email='ana_updated@example.com',
        password_hash='hashed_password',
        created_at=now,
        updated_at=now,
    )
    mock_token_provider.decode_access_token.return_value = {'sub': '1'}
    mock_user_repo.get_user_by_id.return_value = mock_user
    mock_user_repo.get_user.return_value = None
    mock_user_repo.update_user.return_value = mock_user

    response = await user_client.put(
        '/users',
        json={'username': 'ana_updated', 'email': 'ana_updated@example.com'},
        headers={'Authorization': 'Bearer valid-access-token'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['username'] == 'ana_updated'
    assert data['email'] == 'ana_updated@example.com'


@pytest.mark.asyncio
async def test_put_user_unauthorized(user_client: AsyncClient):
    response = await user_client.put(
        '/users',
        json={'username': 'ana_updated', 'email': 'ana_updated@example.com'},
    )

    assert response.status_code in (
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.BAD_REQUEST,
    )


@pytest.mark.asyncio
async def test_patch_password_success(
    user_client: AsyncClient,
    mock_user_repo,
    mock_password_hasher,
    mock_token_provider,
):
    now = datetime.now(timezone.utc)
    mock_user = UserDTO(
        id=1,
        username='ana',
        email='ana@example.com',
        password_hash='new_hashed_password',
        created_at=now,
        updated_at=now,
    )
    mock_token_provider.decode_access_token.return_value = {'sub': '1'}
    mock_user_repo.get_user_by_id.return_value = mock_user
    mock_password_hasher.verify.return_value = True
    mock_password_hasher.hash.return_value = 'new_hashed_password'
    mock_user_repo.change_user_password.return_value = mock_user

    response = await user_client.patch(
        '/users/change-password',
        json={
            'old_password': 'old_password_123',
            'new_password': 'new_password_123',
        },
        headers={'Authorization': 'Bearer valid-access-token'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['id'] == 1


@pytest.mark.asyncio
async def test_patch_password_unauthorized(user_client: AsyncClient):
    response = await user_client.patch(
        '/users/change-password',
        json={
            'old_password': 'old_password_123',
            'new_password': 'new_password_123',
        },
    )

    assert response.status_code in (
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.BAD_REQUEST,
    )
