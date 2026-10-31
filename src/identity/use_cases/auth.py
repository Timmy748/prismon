import secrets
from datetime import datetime, timedelta, timezone

from identity.dtos.auth import AuthenticationDTO, LoginDTO
from identity.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    TokenExpiredException,
)
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.unit_of_work import IIdentityUnitOfWork
from infra.logs import get_logger

logger = get_logger(__name__)


async def login(
    uow: IIdentityUnitOfWork,
    password_hasher: PasswordHasher,
    token_provider: ITokenProvider,
    data: LoginDTO,
) -> AuthenticationDTO:
    user = await uow.user_repository.get_user(email=data.email)
    if not user:
        logger.warning('Login failed: account lookup returned no user')
        raise InvalidCredentialsException()

    if not password_hasher.verify(data.password, user.password_hash):
        logger.warning('Login failed: password verification failed')
        raise InvalidCredentialsException()

    access_token = token_provider.generate_access_token({'sub': str(user.id)})
    raw_refresh_token = secrets.token_urlsafe(32)
    token_hash = token_provider.generate_refresh_token_hash(raw_refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await uow.token_repository.create_refresh_token(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    await uow.commit()
    logger.info('Authentication completed successfully')

    return AuthenticationDTO(
        access_token=access_token,
        refresh_token=raw_refresh_token,
    )


async def refresh_token(
    uow: IIdentityUnitOfWork,
    token_provider: ITokenProvider,
    token: str,
) -> AuthenticationDTO:
    token_hash = token_provider.generate_refresh_token_hash(token)
    token_dto = await uow.token_repository.get_refresh_token_by_token(
        token_hash
    )

    if not token_dto or token_dto.revoked:
        logger.warning('Refresh token rejected: token is missing or revoked')
        raise InvalidTokenException()

    if token_dto.expires_at < datetime.now(timezone.utc):
        logger.warning('Refresh token rejected: token expired')
        raise TokenExpiredException()

    await uow.token_repository.revoke_refresh_token(token_dto.id)

    access_token = token_provider.generate_access_token(
        {'sub': str(token_dto.user_id)}
    )
    new_raw_refresh_token = secrets.token_urlsafe(32)
    new_token_hash = token_provider.generate_refresh_token_hash(
        new_raw_refresh_token
    )
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    await uow.token_repository.create_refresh_token(
        user_id=token_dto.user_id,
        token_hash=new_token_hash,
        expires_at=expires_at,
    )
    await uow.commit()
    logger.info('Refresh token rotated successfully')

    return AuthenticationDTO(
        access_token=access_token,
        refresh_token=new_raw_refresh_token,
    )


async def logout(
    uow: IIdentityUnitOfWork,
    user_id: int,
) -> None:
    await uow.token_repository.revoke_refresh_tokens_by_user_id(user_id)
    await uow.commit()
    logger.info('Refresh tokens revoked for user')
