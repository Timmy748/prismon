from datetime import datetime, timedelta, timezone
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from identity.dtos.token import RefreshTokenDTO
from identity.dtos.user import UserDTO
from identity.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
)


@pytest.mark.asyncio
async def test_post_login_success(
    auth_client: AsyncClient,
    mock_user_repo,
    mock_token_repo,
    mock_password_hasher,
    mock_token_provider,
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
    mock_token_dto = RefreshTokenDTO(
        id=1,
        user_id=1,
        token_hash='hashed_refresh_token',
        expires_at=now,
        revoked=False,
    )

    mock_user_repo.get_user.return_value = mock_user
    mock_password_hasher.verify.return_value = True
    mock_token_provider.generate_access_token.return_value = 'access-token-123'
    mock_token_provider.generate_refresh_token_hash.return_value = (
        'hashed_refresh_token'
    )
    mock_token_repo.create_refresh_token.return_value = mock_token_dto

    response = await auth_client.post(
        '/login',
        json={'email': 'ana@example.com', 'password': 'securepassword123'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['access_token'] == 'access-token-123'
    assert 'refresh_token' in data


@pytest.mark.asyncio
async def test_post_login_identity_exception_handled(
    auth_client: AsyncClient,
    mock_user_repo,
):

    mock_user_repo.get_user.side_effect = InvalidCredentialsException()

    response = await auth_client.post(
        '/login',
        json={'email': 'wrong@example.com', 'password': 'wrongpassword'},
    )

    assert response.status_code != HTTPStatus.OK


@pytest.mark.asyncio
async def test_post_refresh_token_success(
    auth_client: AsyncClient,
    mock_token_repo,
    mock_token_provider,
):
    now = datetime.now(timezone.utc)
    mock_token_dto = RefreshTokenDTO(
        id=1,
        user_id=1,
        token_hash='hashed_refresh_token',
        expires_at=now + timedelta(days=1),
        revoked=False,
    )

    mock_token_provider.generate_refresh_token_hash.return_value = (
        'hashed_refresh_token'
    )
    mock_token_repo.get_refresh_token_by_token.return_value = mock_token_dto
    mock_token_provider.generate_access_token.return_value = 'new-access-token'
    mock_token_repo.create_refresh_token.return_value = mock_token_dto

    response = await auth_client.post(
        '/refresh-token',
        json={'refresh_token': 'valid-refresh-token'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['access_token'] == 'new-access-token'
    assert 'refresh_token' in data


@pytest.mark.asyncio
async def test_post_refresh_token_identity_exception_handled(
    auth_client: AsyncClient,
    mock_token_repo,
    mock_token_provider,
):

    mock_token_provider.generate_refresh_token_hash.return_value = (
        'invalid_hash'
    )
    mock_token_repo.get_refresh_token_by_token.side_effect = (
        InvalidTokenException()
    )

    response = await auth_client.post(
        '/refresh-token',
        json={'refresh_token': 'invalid-token'},
    )

    assert response.status_code != HTTPStatus.OK


@pytest.mark.asyncio
async def test_post_logout_success(
    auth_client: AsyncClient,
    mock_user_repo,
    mock_token_repo,
    mock_token_provider,
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

    mock_token_provider.decode_access_token.return_value = {'sub': '1'}
    mock_user_repo.get_user_by_id.return_value = mock_user
    mock_token_repo.revoke_refresh_tokens_by_user_id.return_value = None

    response = await auth_client.post(
        '/logout',
        headers={'Authorization': 'Bearer valid-access-token'},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b''


@pytest.mark.asyncio
async def test_post_logout_unauthorized(auth_client: AsyncClient):
    response = await auth_client.post('/logout')

    assert response.status_code in (
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.BAD_REQUEST,
    )
