# ruff: noqa: PLR0913, PLR0917
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import Response

from core.logs import get_logger
from project.clients.client_user import IUserClient
from project.dtos.asset import CreateAssetDTO, UpdateAssetDTO
from project.dtos.page import PaginationDTO
from project.entities.asset import AssetStatus
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.asset import AssetPageSchema, AssetSchema
from project.storage import IStorage
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.assets import (
    add_asset,
    delete_asset,
    get_assets,
    update_asset,
)
from project.utils.pagination import decode_cursor, encode_cursor

logger = get_logger(__name__)


def create_assets_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork],
    storage_factory: Callable[[], IStorage],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(prefix='/projects/{project_id}/assets', tags=['assets'])

    async def resolve_current_user(cookies):
        access_token = cookies.get('jwt')
        if not access_token:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(access_token)

    @router.get('', response_model=AssetPageSchema)
    async def list_assets(
        request: Request,
        project_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
        type: str | None = Query(default=None),
        status: AssetStatus | None = Query(default=None),
    ):
        logger.info('Asset route started: operation=list')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                page = await get_assets(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                    type,
                    status,
                )
            result = AssetPageSchema(
                items=[AssetSchema.from_dto(item) for item in page.items],
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
            logger.info(
                'Asset route completed: operation=list item_count=%s',
                len(page.items),
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.post('', response_model=AssetSchema, status_code=HTTPStatus.CREATED)
    async def post_asset(
        request: Request,
        project_id: int,
        type: str = Form(...),
        description: str | None = Form(default=None),
        file: UploadFile = File(...),
    ):
        logger.info('Asset route started: operation=create')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await add_asset(
                    unit_of_work,
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
            result = AssetSchema.from_dto(dto)
            logger.info('Asset route completed: operation=create')
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{asset_id}', response_model=AssetSchema)
    async def put_asset(
        request: Request,
        project_id: int,
        asset_id: int,
        type: str | None = Form(default=None),
        description: str | None = Form(default=None),
        file: UploadFile | None = File(default=None),
    ):
        logger.info('Asset route started: operation=update')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await update_asset(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    asset_id,
                    UpdateAssetDTO(type=type, description=description),
                    await file.read() if file is not None else None,
                )
            result = AssetSchema.from_dto(dto)
            logger.info('Asset route completed: operation=update')
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete('/{asset_id}', status_code=HTTPStatus.NO_CONTENT)
    async def remove_asset(
        request: Request,
        project_id: int,
        asset_id: int,
    ):
        logger.info('Asset route started: operation=delete')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await delete_asset(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    asset_id,
                )
            logger.info('Asset route completed: operation=delete')
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    return router
