import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher

from identity.dtos.auth import AuthenticationDTO, LoginDTO
from identity.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
)
from identity.repositories.token import IRefreshTokenRepository
from identity.repositories.user import IUserRepository
from identity.security.jwt import ITokenProvider


async def login(
    user_repo: IUserRepository,
    token_repo: IRefreshTokenRepository,
    password_hasher: PasswordHasher,
    token_provider: ITokenProvider,
    data: LoginDTO,
) -> AuthenticationDTO:
    user = await user_repo.get_user(email=data.email)
    if not user:
        raise InvalidCredentialsException()

    if not password_hasher.verify(data.password, user.password_hash):
        raise InvalidCredentialsException()

    access_token = token_provider.generate_access_token({'sub': str(user.id)})
    raw_refresh_token = secrets.token_urlsafe(32)
    token_hash = token_provider.generate_refresh_token_hash(raw_refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await token_repo.create_refresh_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    return AuthenticationDTO(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


async def refresh_token(
    token_repo: IRefreshTokenRepository,
    token_provider: ITokenProvider,
    token: str,
) -> AuthenticationDTO:
    token_hash = token_provider.generate_refresh_token_hash(token)
    token_dto = await token_repo.get_refresh_token_by_token(token_hash)

    if not token_dto or token_dto.revoked:
        raise InvalidTokenException()

    if token_dto.expires_at < datetime.now(timezone.utc):
        raise TokenExpiredException()

    await token_repo.revoke_refresh_token(token_dto.id)

    access_token = token_provider.generate_access_token(
        {'sub': str(token_dto.user_id)}
    )
    new_raw_refresh_token = secrets.token_urlsafe(32)
    new_token_hash = token_provider.generate_refresh_token_hash(
        new_raw_refresh_token
    )
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await token_repo.create_refresh_token(
        user_id=token_dto.user_id,
        token_hash=new_token_hash,
        expires_at=expires_at,
    )

    return AuthenticationDTO(
        access_token=access_token,
        refresh_token=new_raw_refresh_token,
    )


async def logout(
    token_repo: IRefreshTokenRepository,
    user_id: int,
) -> None:
    await token_repo.revoke_refresh_tokens_by_user_id(user_id)
