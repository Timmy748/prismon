from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from identity.dtos.auth import LoginDTO
from identity.dtos.user import UserDTO
from identity.exceptions import IdentityException, InvalidTokenException
from identity.handlers.errors import handle_identity_error
from identity.repositories.token import (
    IRefreshTokenRepository,
)
from identity.repositories.user import IUserRepository
from identity.schemas.auth import (
    AuthenticationSchema,
    LoginSchema,
    RefreshTokenSchema,
)
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.use_cases.auth import login, logout, refresh_token
from identity.use_cases.user import get_current_user


def create_auth_router(
    password_hasher_factory: Callable[[], PasswordHasher],
    token_provider_factory: Callable[[], ITokenProvider],
    user_repository_factory: Callable[[], Awaitable[IUserRepository]],
    token_repository_factory: Callable[[], Awaitable[IRefreshTokenRepository]],
) -> APIRouter:
    router = APIRouter(tags=['auth'])
    bearer = HTTPBearer(auto_error=False)

    async def authenticated_user(
        credentials: HTTPAuthorizationCredentials | None,
    ) -> UserDTO:
        if credentials is None:
            raise InvalidTokenException()
        return await get_current_user(
            await user_repository_factory(),
            token_provider_factory(),
            credentials.credentials,
        )

    @router.post('/login', response_model=AuthenticationSchema)
    async def post_login(
        data: LoginSchema,
    ) -> AuthenticationSchema | JSONResponse:
        try:
            user_repo = await user_repository_factory()
            token_repo = await token_repository_factory()
            result = await login(
                user_repo,
                token_repo,
                password_hasher_factory(),
                token_provider_factory(),
                LoginDTO(email=str(data.email), password=data.password),
            )
            return AuthenticationSchema(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
            )
        except IdentityException as error:
            return handle_identity_error(error)

    @router.post('/refresh-token', response_model=AuthenticationSchema)
    async def post_refresh_token(
        data: RefreshTokenSchema,
    ) -> AuthenticationSchema | JSONResponse:
        try:
            token_repo = await token_repository_factory()
            result = await refresh_token(
                token_repo,
                token_provider_factory(),
                data.refresh_token,
            )
            return AuthenticationSchema(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
            )
        except IdentityException as error:
            return handle_identity_error(error)

    @router.post(
        '/logout',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
        response_class=Response,
    )
    async def post_logout(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> Response:
        try:
            user = await authenticated_user(credentials)
            token_repo = await token_repository_factory()
            await logout(token_repo, user.id)
        except IdentityException as error:
            return handle_identity_error(error)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    return router
