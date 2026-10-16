from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from identity.dtos.auth import LoginDTO
from identity.dtos.user import UserDTO
from identity.exceptions import IdentityException, InvalidTokenException
from identity.handlers.errors import handle_identity_error
from identity.repositories.token import (
    IRefreshTokenRepository,
)
from identity.repositories.user import IUserRepository
from identity.schemas.auth import (
    LoginSchema,
)
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.settings import get_settings
from identity.use_cases.auth import login, logout, refresh_token
from identity.use_cases.user import get_current_user


def create_auth_router(
    password_hasher_factory: Callable[[], PasswordHasher],
    token_provider_factory: Callable[[], ITokenProvider],
    user_repository_factory: Callable[[], Awaitable[IUserRepository]],
    token_repository_factory: Callable[[], Awaitable[IRefreshTokenRepository]],
) -> APIRouter:
    router = APIRouter(tags=['auth'])

    async def resolve_identity_user(access_token: str) -> UserDTO:
        return await get_current_user(
            await user_repository_factory(),
            token_provider_factory(),
            access_token,
        )

    async def resolve_current_user(cookies) -> UserDTO:
        access_token = cookies.get('jwt')
        if not access_token:
            raise InvalidTokenException()
        return await resolve_identity_user(access_token)

    @router.post('/login')
    async def post_login(data: LoginSchema) -> JSONResponse:
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
            response = JSONResponse({'message': 'Login sucess'})
            response.set_cookie(
                key='jwt',
                value=result.access_token,
                secure=True,
                httponly=True,
                samesite='lax',
                max_age=get_settings().JWT_EXPIRES_IN_MINUTES * 60,
                path='/',
            )

            response.set_cookie(
                key='refresh_token',
                value=result.refresh_token,
                secure=True,
                httponly=True,
                samesite='lax',
                max_age=7 * 24 * 60 * 60,
                path='/',
            )

            return response
        except IdentityException as error:
            return handle_identity_error(error)

    @router.post('/refresh-token')
    async def post_refresh_token(request: Request) -> JSONResponse:
        try:
            token = request.cookies.get('refresh_token', '')
            token_repo = await token_repository_factory()
            result = await refresh_token(
                token_repo,
                token_provider_factory(),
                token,
            )
            response = JSONResponse({'message': 'Refresh sucess'})
            response.set_cookie(
                key='jwt',
                value=result.access_token,
                secure=True,
                httponly=True,
                samesite='lax',
                max_age=get_settings().JWT_EXPIRES_IN_MINUTES * 60,
                path='/',
            )

            response.set_cookie(
                key='refresh_token',
                value=result.refresh_token,
                secure=True,
                httponly=True,
                samesite='lax',
                max_age=7 * 24 * 60 * 60,
                path='/',
            )

            return response
        except IdentityException as error:
            return handle_identity_error(error)

    @router.post(
        '/logout',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
        response_class=Response,
    )
    async def post_logout(
        response: Response,
        request: Request,
    ) -> Response:
        try:
            user = await resolve_current_user(request.cookies)
            token_repo = await token_repository_factory()
            await logout(token_repo, user.id)
            response.delete_cookie(key='jwt', path='/')
            response.delete_cookie(key='refresh_token', path='/')
            response.status_code = HTTPStatus.NO_CONTENT
        except IdentityException as error:
            return handle_identity_error(error)
        return response

    return router
