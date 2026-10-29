from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from project.clients.client_user import IUserClient
from project.dtos.api_key_hint import ApiKeyHintDTO
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.api_key import ApiKeyHintSchema, CreateApiKeySchema
from project.security.api_key import (
    IApiKeyEncryption,
    create_api_key_encryption,
)
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.api_key import (
    create_member_api_key,
    create_project_api_key,
    delete_api_key,
    list_member_api_keys,
    list_project_api_keys,
)
from project.utils.pagination import PageSchema, page_schema, pagination_dto


def create_api_keys_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork],
    user_client_factory: Callable[[], IUserClient],
    encryption_factory: Callable[
        [], IApiKeyEncryption
    ] = create_api_key_encryption,
) -> APIRouter:
    router = APIRouter(
        prefix='/projects/{project_id}', tags=['project api keys']
    )

    async def resolve_current_user(cookies):
        access_token = cookies.get('jwt')
        if not access_token:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(access_token)

    @router.post(
        '/members/me/api-keys',
        response_model=ApiKeyHintSchema,
        status_code=HTTPStatus.CREATED,
    )
    async def post_member_api_key(
        request: Request, project_id: int, data: CreateApiKeySchema
    ) -> ApiKeyHintDTO | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as uow:
                return await create_member_api_key(
                    uow,
                    project_id,
                    user.id,
                    data.provider,
                    data.api_key.get_secret_value(),
                    encryption_factory(),
                )
        except ProjectException as error:
            return handle_project_error(error)

    @router.get(
        '/members/me/api-keys', response_model=PageSchema[ApiKeyHintSchema]
    )
    async def get_member_api_keys(
        request: Request,
        project_id: int,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ) -> PageSchema[ApiKeyHintDTO] | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as uow:
                page = await list_member_api_keys(
                    uow, project_id, user.id, pagination_dto(cursor, limit)
                )
                return page_schema(page)
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '/api-keys',
        response_model=ApiKeyHintSchema,
        status_code=HTTPStatus.CREATED,
    )
    async def post_project_api_key(
        request: Request, project_id: int, data: CreateApiKeySchema
    ) -> ApiKeyHintDTO | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as uow:
                return await create_project_api_key(
                    uow,
                    project_id,
                    user.id,
                    data.provider,
                    data.api_key.get_secret_value(),
                    encryption_factory(),
                )
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/api-keys', response_model=PageSchema[ApiKeyHintSchema])
    async def get_project_api_keys(
        request: Request,
        project_id: int,
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = None,
    ) -> PageSchema[ApiKeyHintDTO] | JSONResponse:
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as uow:
                page = await list_project_api_keys(
                    uow, project_id, user.id, pagination_dto(cursor, limit)
                )
                return page_schema(page)
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete(
        '/api-keys/{api_key_id}',
        status_code=HTTPStatus.NO_CONTENT,
        response_model=None,
    )
    async def remove_api_key(
        request: Request, project_id: int, api_key_id: int
    ) -> JSONResponse | None:
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as uow:
                await delete_api_key(uow, project_id, user.id, api_key_id)
                return None
        except ProjectException as error:
            return handle_project_error(error)

    return router
