# ruff: noqa: PLR0913, PLR0915, PLR0917
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse, Response

from infra.logs import get_logger
from project.clients.client_user import IUserClient, create_identity_client
from project.dtos.asset import StartAssetUploadDTO, UpdateAssetDTO
from project.dtos.page import PaginationDTO
from project.entities.asset import AssetStatus
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.asset import (
    AssetEventPageSchema,
    AssetEventSchema,
    AssetPageSchema,
    AssetSchema,
    AssetUploadSchema,
    ReplaceAssetUploadRequest,
    StartAssetUploadRequest,
    UpdateAssetRequest,
)
from project.storage import IStorage, create_storage
from project.unit_of_work import IProjectUnitOfWork, create_project_unit_of_work
from project.use_cases.assets import (
    delete_asset,
    download_asset,
    get_asset_events,
    get_asset_file_url,
    get_assets,
    start_asset_replacement,
    start_asset_upload,
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

    @router.post(
        '',
        response_model=AssetUploadSchema,
        status_code=HTTPStatus.CREATED,
    )
    async def post_asset(
        request: Request,
        project_id: int,
        data: StartAssetUploadRequest,
    ):
        logger.info('Asset route started: operation=create')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await start_asset_upload(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    StartAssetUploadDTO(
                        type=data.type,
                        name=data.name,
                        original_filename=data.original_filename,
                        description=data.description or '',
                        content_type=data.content_type,
                    ),
                )
            logger.info('Asset route completed: operation=create')
            return AssetUploadSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '/{asset_id}/uploads',
        response_model=AssetUploadSchema,
        status_code=HTTPStatus.ACCEPTED,
    )
    async def post_asset_upload(
        request: Request,
        project_id: int,
        asset_id: int,
        data: ReplaceAssetUploadRequest,
    ):
        logger.info('Asset route started: operation=upload')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await start_asset_replacement(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    asset_id,
                    data.content_type,
                    original_filename=data.original_filename,
                )
            logger.info('Asset route completed: operation=upload')
            return AssetUploadSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{asset_id}', response_model=AssetSchema)
    async def put_asset(
        request: Request,
        project_id: int,
        asset_id: int,
        data: UpdateAssetRequest,
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
                    UpdateAssetDTO(
                        name=data.name,
                        type=data.type,
                        description=data.description,
                    ),
                )
            result = AssetSchema.from_dto(dto)
            logger.info('Asset route completed: operation=update')
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/{asset_id}/history', response_model=AssetEventPageSchema)
    async def list_asset_history(
        request: Request,
        project_id: int,
        asset_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ):
        logger.info('Asset route started: operation=history')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                page = await get_asset_events(
                    unit_of_work,
                    project_id,
                    user.id,
                    asset_id,
                    PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                )
            result = AssetEventPageSchema(
                items=[AssetEventSchema.from_dto(item) for item in page.items],
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
            logger.info('Asset route completed: operation=history')
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

    @router.get('/{asset_id}/file')
    async def redirect_asset_file(
        request: Request,
        project_id: int,
        asset_id: int,
    ):
        logger.info('Asset route started: operation=file')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                url = await get_asset_file_url(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    asset_id,
                )
            logger.info('Asset route completed: operation=file')
            return RedirectResponse(
                url=url, status_code=HTTPStatus.TEMPORARY_REDIRECT
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/{asset_id}/download')
    async def redirect_asset_download(
        request: Request,
        project_id: int,
        asset_id: int,
    ):
        logger.info('Asset route started: operation=download')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                url = await download_asset(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    asset_id,
                )
            logger.info('Asset route completed: operation=download')
            return RedirectResponse(
                url=url, status_code=HTTPStatus.TEMPORARY_REDIRECT
            )
        except ProjectException as error:
            return handle_project_error(error)

    return router


router = create_assets_router(
    create_project_unit_of_work,
    create_storage,
    create_identity_client,
)
