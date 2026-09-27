from datetime import datetime, timedelta, timezone

import pytest

from identity.dtos.auth import AuthenticationDTO, LoginDTO
from identity.dtos.token import RefreshTokenDTO
from identity.dtos.user import UserDTO
from identity.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
)
from identity.use_cases.auth import login, logout, refresh_token


@pytest.mark.asyncio
async def test_login_success(
    mock_user_repo, mock_token_repo, mock_password_hasher, mock_token_provider
):
    user_dto = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = user_dto
    mock_password_hasher.verify.return_value = True
    mock_token_provider.generate_access_token.return_value = 'access_token'
    mock_token_provider.generate_refresh_token_hash.return_value = 'token_hash'

    login_dto = LoginDTO(email='test@example.com', password='password123')
    result = await login(
        user_repo=mock_user_repo,
        token_repo=mock_token_repo,
        password_hasher=mock_password_hasher,
        token_provider=mock_token_provider,
        data=login_dto,
    )

    assert isinstance(result, AuthenticationDTO)
    assert result.access_token == 'access_token'
    assert result.refresh_token is not None


@pytest.mark.asyncio
async def test_login_user_not_found(
    mock_user_repo, mock_token_repo, mock_password_hasher, mock_token_provider
):
    mock_user_repo.get_user.return_value = None
    login_dto = LoginDTO(email='notfound@example.com', password='password123')

    with pytest.raises(InvalidCredentialsException):
        await login(
            user_repo=mock_user_repo,
            token_repo=mock_token_repo,
            password_hasher=mock_password_hasher,
            token_provider=mock_token_provider,
            data=login_dto,
        )


@pytest.mark.asyncio
async def test_login_invalid_password(
    mock_user_repo, mock_token_repo, mock_password_hasher, mock_token_provider
):
    user_dto = UserDTO(
        id=1,
        username='testuser',
        email='test@example.com',
        password_hash='hashed_pw',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_user.return_value = user_dto
    mock_password_hasher.verify.return_value = False

    login_dto = LoginDTO(email='test@example.com', password='wrongpassword')

    with pytest.raises(InvalidCredentialsException):
        await login(
            user_repo=mock_user_repo,
            token_repo=mock_token_repo,
            password_hasher=mock_password_hasher,
            token_provider=mock_token_provider,
            data=login_dto,
        )


@pytest.mark.asyncio
async def test_refresh_token_success(mock_token_repo, mock_token_provider):
    token_dto = RefreshTokenDTO(
        id=10,
        user_id=1,
        token_hash='hashed_token',
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        revoked=False,
    )
    mock_token_provider.generate_refresh_token_hash.return_value = (
        'hashed_token'
    )
    mock_token_repo.get_refresh_token_by_token.return_value = token_dto
    mock_token_provider.generate_access_token.return_value = 'new_access_token'

    result = await refresh_token(
        token_repo=mock_token_repo,
        token_provider=mock_token_provider,
        token='raw_refresh_token',
    )

    assert isinstance(result, AuthenticationDTO)
    assert result.access_token == 'new_access_token'
    assert result.refresh_token is not None


@pytest.mark.asyncio
async def test_refresh_token_not_found_or_revoked(
    mock_token_repo, mock_token_provider
):
    mock_token_provider.generate_refresh_token_hash.return_value = (
        'hashed_token'
    )
    mock_token_repo.get_refresh_token_by_token.return_value = None

    with pytest.raises(InvalidTokenException):
        await refresh_token(
            token_repo=mock_token_repo,
            token_provider=mock_token_provider,
            token='invalid_token',
        )


@pytest.mark.asyncio
async def test_refresh_token_expired(mock_token_repo, mock_token_provider):
    token_dto = RefreshTokenDTO(
        id=10,
        user_id=1,
        token_hash='hashed_token',
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        revoked=False,
    )
    mock_token_provider.generate_refresh_token_hash.return_value = (
        'hashed_token'
    )
    mock_token_repo.get_refresh_token_by_token.return_value = token_dto

    with pytest.raises(TokenExpiredException):
        await refresh_token(
            token_repo=mock_token_repo,
            token_provider=mock_token_provider,
            token='expired_token',
        )


@pytest.mark.asyncio
async def test_logout_success(mock_token_repo):
    await logout(token_repo=mock_token_repo, user_id=1)

    mock_token_repo.revoke_refresh_tokens_by_user_id.assert_called_once_with(1)
