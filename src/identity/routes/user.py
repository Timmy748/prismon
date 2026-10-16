from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from identity.dtos.user import (
    CreateUserDTO,
    UpdateUserDTO,
    UpdateUserPasswordDTO,
    UserDTO,
)
from identity.exceptions import IdentityException, InvalidTokenException
from identity.handlers.errors import handle_identity_error
from identity.repositories.user import IUserRepository
from identity.schemas.user import (
    CreateUserSchema,
    UpdateUserPasswordSchema,
    UpdateUserSchema,
    UserSchema,
)
from identity.security.jwt import ITokenProvider
from identity.security.password_hasher import PasswordHasher
from identity.use_cases.user import (
    change_password,
    create_user,
    get_current_user,
    get_user_by_id,
    update_user,
)


def create_user_router(
    password_hasher_factory: Callable[[], PasswordHasher],
    token_provider_factory: Callable[[], ITokenProvider],
    repository_factory: Callable[[], Awaitable[IUserRepository]],
) -> APIRouter:
    router = APIRouter(prefix='/users', tags=['users'])

    async def resolve_identity_user(access_token: str) -> UserDTO:
        return await get_current_user(
            await repository_factory(),
            token_provider_factory(),
            access_token,
        )

    async def resolve_current_user(cookies) -> UserDTO:
        access_token = cookies.get('jwt')
        if not access_token:
            raise InvalidTokenException()
        return await resolve_identity_user(access_token)

    @router.post('', response_model=UserSchema, status_code=HTTPStatus.CREATED)
    async def post_user(
        data: CreateUserSchema,
    ) -> UserDTO | JSONResponse:
        try:
            repo = await repository_factory()
            return await create_user(
                repo,
                password_hasher_factory(),
                CreateUserDTO(
                    username=data.username,
                    email=data.email,
                    password_hash=data.password_hash,
                ),
            )
        except IdentityException as error:
            return handle_identity_error(error)

    @router.get('/{user_id}', response_model=UserSchema)
    async def get_user(
        user_id: int,
    ) -> UserDTO | JSONResponse:
        try:
            repo = await repository_factory()
            return await get_user_by_id(repo, user_id)
        except IdentityException as error:
            return handle_identity_error(error)

    @router.put('', response_model=UserSchema)
    async def put_user(
        request: Request,
        data: UpdateUserSchema,
    ) -> UserDTO | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            repo = await repository_factory()
            return await update_user(
                repo,
                user.id,
                UpdateUserDTO(username=data.username, email=data.email),
            )
        except IdentityException as error:
            return handle_identity_error(error)

    @router.patch('/change-password', response_model=UserSchema)
    async def patch_password(
        request: Request,
        data: UpdateUserPasswordSchema,
    ) -> UserDTO | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            repo = await repository_factory()
            return await change_password(
                repo,
                password_hasher_factory(),
                user.id,
                UpdateUserPasswordDTO(
                    old_password=data.old_password,
                    new_password=data.new_password,
                ),
            )
        except IdentityException as error:
            return handle_identity_error(error)

    return router
