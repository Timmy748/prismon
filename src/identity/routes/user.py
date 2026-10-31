from collections.abc import Callable
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
from identity.schemas.user import (
    CreateUserSchema,
    UpdateUserPasswordSchema,
    UpdateUserSchema,
    UserSchema,
)
from identity.security.jwt import ITokenProvider, create_token_provider
from identity.security.password_hasher import (
    PasswordHasher,
    create_password_hasher,
)
from identity.unit_of_work import (
    IIdentityUnitOfWork,
    create_identity_unit_of_work,
)
from identity.use_cases.user import (
    change_password,
    create_user,
    get_current_user,
    get_user_by_id,
    update_user,
)
from infra.logs import get_logger

logger = get_logger(__name__)


def create_user_router(
    password_hasher_factory: Callable[[], PasswordHasher],
    token_provider_factory: Callable[[], ITokenProvider],
    unit_of_work_factory: Callable[[], IIdentityUnitOfWork] = (
        create_identity_unit_of_work
    ),
) -> APIRouter:
    router = APIRouter(prefix='/users', tags=['users'])

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

    @router.post('', response_model=UserSchema, status_code=HTTPStatus.CREATED)
    async def post_user(
        data: CreateUserSchema,
    ) -> UserDTO | JSONResponse:
        try:
            async with unit_of_work_factory() as uow:
                return await create_user(
                    uow,
                    password_hasher_factory(),
                    CreateUserDTO(
                        username=data.username,
                        email=data.email,
                        password_hash=data.password_hash,
                    ),
                )
        except IdentityException as error:
            logger.warning('User creation rejected: %s', type(error).__name__)
            return handle_identity_error(error)

    @router.get('/{user_id}', response_model=UserSchema)
    async def get_user(
        user_id: int,
    ) -> UserDTO | JSONResponse:
        try:
            async with unit_of_work_factory() as uow:
                return await get_user_by_id(uow, user_id)
        except IdentityException as error:
            logger.warning('User lookup rejected: %s', type(error).__name__)
            return handle_identity_error(error)

    @router.put('', response_model=UserSchema)
    async def put_user(
        request: Request,
        data: UpdateUserSchema,
    ) -> UserDTO | JSONResponse:
        try:
            async with unit_of_work_factory() as uow:
                user = await resolve_current_user(uow, request.cookies)
                return await update_user(
                    uow,
                    user.id,
                    UpdateUserDTO(username=data.username, email=data.email),
                )
        except IdentityException as error:
            logger.warning('User update rejected: %s', type(error).__name__)
            return handle_identity_error(error)

    @router.patch('/change-password', response_model=UserSchema)
    async def patch_password(
        request: Request,
        data: UpdateUserPasswordSchema,
    ) -> UserDTO | JSONResponse:
        try:
            async with unit_of_work_factory() as uow:
                user = await resolve_current_user(uow, request.cookies)
                return await change_password(
                    uow,
                    password_hasher_factory(),
                    user.id,
                    UpdateUserPasswordDTO(
                        old_password=data.old_password,
                        new_password=data.new_password,
                    ),
                )
        except IdentityException as error:
            logger.warning('Password change rejected: %s', type(error).__name__)
            return handle_identity_error(error)

    return router


router = create_user_router(
    create_password_hasher,
    create_token_provider,
    create_identity_unit_of_work,
)
