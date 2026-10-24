from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from core.logs import get_logger
from identity.dtos.auth import LoginDTO
from identity.dtos.user import UserDTO
from identity.exceptions import IdentityException, InvalidTokenException
from identity.handlers.errors import handle_identity_error
from identity.schemas.auth import LoginSchema
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.settings import get_settings
from identity.unit_of_work import (
    IIdentityUnitOfWork,
    create_identity_unit_of_work,
)
from identity.use_cases.auth import login, logout, refresh_token
from identity.use_cases.user import get_current_user

logger = get_logger(__name__)


def create_auth_router(
    password_hasher_factory: Callable[[], PasswordHasher],
    token_provider_factory: Callable[[], ITokenProvider],
    unit_of_work_factory: Callable[[], IIdentityUnitOfWork] = (
        create_identity_unit_of_work
    ),
) -> APIRouter:
    router = APIRouter(tags=['auth'])

    async def resolve_identity_user(
        uow: IIdentityUnitOfWork, access_token: str
    ) -> UserDTO:
        return await get_current_user(
            uow,
            token_provider_factory(),
            access_token,
        )

    async def resolve_current_user(
        uow: IIdentityUnitOfWork, cookies
    ) -> UserDTO:
        access_token = cookies.get('jwt')
        if not access_token:
            raise InvalidTokenException()
        return await resolve_identity_user(uow, access_token)

    @router.post('/login')
    async def post_login(data: LoginSchema) -> JSONResponse:
        try:
            async with unit_of_work_factory() as uow:
                result = await login(
                    uow,
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

            logger.info('Login successful')
            return response
        except IdentityException as error:
            logger.warning('Login rejected: %s', type(error).__name__)
            return handle_identity_error(error)

    @router.post('/refresh-token')
    async def post_refresh_token(request: Request) -> JSONResponse:
        try:
            token = request.cookies.get('refresh_token', '')
            async with unit_of_work_factory() as uow:
                result = await refresh_token(
                    uow,
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

            logger.info('Refresh token rotated successfully')
            return response
        except IdentityException as error:
            logger.warning(
                'Refresh token request rejected: %s', type(error).__name__
            )
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
            async with unit_of_work_factory() as uow:
                user = await resolve_current_user(uow, request.cookies)
                await logout(uow, user.id)
            response.delete_cookie(key='jwt', path='/')
            response.delete_cookie(key='refresh_token', path='/')
            response.status_code = HTTPStatus.NO_CONTENT
            logger.info('Logout successful')
        except IdentityException as error:
            logger.warning('Logout rejected: %s', type(error).__name__)
            return handle_identity_error(error)
        return response

    return router
