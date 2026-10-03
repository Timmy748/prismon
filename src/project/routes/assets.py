# ruff: noqa: PLR0913, PLR0917
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from project.clients.client_user import IUserClient
from project.dtos.asset import CreateAssetDTO, UpdateAssetDTO
from project.dtos.page import PaginationDTO
from project.entities.asset import AssetStatus
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.repositories.asset import IAssetRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.schemas.asset import AssetPageSchema, AssetSchema
from project.storage import IStorage
from project.use_cases.assets import (
    add_asset,
    delete_asset,
    get_assets,
    update_asset,
)
from project.utils.pagination import decode_cursor, encode_cursor


def create_assets_router(
    project_repository_factory: Callable[[], Awaitable[IProjectRepository]],
    member_repository_factory: Callable[[], Awaitable[IMemberRepository]],
    asset_repository_factory: Callable[[], Awaitable[IAssetRepository]],
    storage_factory: Callable[[], IStorage],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(prefix='/projects/{project_id}/assets', tags=['assets'])
    bearer = HTTPBearer(auto_error=False)

    async def current_user(
        credentials: HTTPAuthorizationCredentials | None,
    ):
        if credentials is None:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(
            credentials.credentials
        )

    @router.get('', response_model=AssetPageSchema)
    async def list_assets(
        project_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
        type: str | None = Query(default=None),
        status: AssetStatus | None = Query(default=None),
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            page = await get_assets(
                await project_repository_factory(),
                await member_repository_factory(),
                await asset_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                type,
                status,
            )
            return AssetPageSchema(
                items=[AssetSchema.from_dto(item) for item in page.items],
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.post('', response_model=AssetSchema, status_code=HTTPStatus.CREATED)
    async def post_asset(
        project_id: int,
        type: str = Form(...),
        description: str | None = Form(default=None),
        file: UploadFile = File(...),
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            dto = await add_asset(
                await project_repository_factory(),
                await member_repository_factory(),
                await asset_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                CreateAssetDTO(
                    file='',
                    asset='',
                    type=type,
                    name='',
                    description=description or '',
                ),
                await file.read(),
            )
            return AssetSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{asset_id}', response_model=AssetSchema)
    async def put_asset(
        project_id: int,
        asset_id: int,
        type: str | None = Form(default=None),
        description: str | None = Form(default=None),
        file: UploadFile | None = File(default=None),
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            dto = await update_asset(
                await project_repository_factory(),
                await member_repository_factory(),
                await asset_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                asset_id,
                UpdateAssetDTO(type=type, description=description),
                await file.read() if file is not None else None,
            )
            return AssetSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete('/{asset_id}', status_code=HTTPStatus.NO_CONTENT)
    async def remove_asset(
        project_id: int,
        asset_id: int,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            await delete_asset(
                await project_repository_factory(),
                await member_repository_factory(),
                await asset_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                asset_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    return router
