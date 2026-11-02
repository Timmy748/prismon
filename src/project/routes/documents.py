# ruff: noqa: PLR0913, PLR0915, PLR0917
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse, Response

from infra.logs import get_logger
from project.clients.client_user import IUserClient, create_identity_client
from project.dtos.document import (
    StartDocumentUploadDTO,
    UpdateDocumentDTO,
)
from project.dtos.page import PaginationDTO
from project.entities.document import DocumentStatus
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.document import (
    DocumentEventPageSchema,
    DocumentEventSchema,
    DocumentPageSchema,
    DocumentSchema,
    DocumentUploadSchema,
    ReplaceDocumentUploadRequest,
    StartDocumentUploadRequest,
    UpdateDocumentRequest,
)
from project.storage import IStorage, create_storage
from project.unit_of_work import IProjectUnitOfWork, create_project_unit_of_work
from project.use_cases.documents import (
    delete_document,
    download_document,
    get_document_events,
    get_document_file_url,
    get_documents,
    start_document_replacement,
    start_document_upload,
    update_document,
)
from project.utils.pagination import decode_cursor, encode_cursor

logger = get_logger(__name__)


def create_documents_router(
    unit_of_work_factory: Callable[[], IProjectUnitOfWork],
    storage_factory: Callable[[], IStorage],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(
        prefix='/projects/{project_id}/documents', tags=['documents']
    )

    async def resolve_current_user(cookies):
        access_token = cookies.get('jwt')
        if not access_token:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(access_token)

    @router.get('', response_model=DocumentPageSchema)
    async def list_documents(
        request: Request,
        project_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
        name: str | None = Query(default=None),
        status: DocumentStatus | None = Query(default=None),
    ):
        logger.info('Document route started: operation=list')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                page = await get_documents(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                    name,
                    status,
                )
            result = DocumentPageSchema(
                items=[DocumentSchema.from_dto(item) for item in page.items],
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
            logger.info(
                'Document route completed: operation=list item_count=%s',
                len(page.items),
            )
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '',
        response_model=DocumentUploadSchema,
        status_code=HTTPStatus.CREATED,
    )
    async def post_document(
        request: Request,
        project_id: int,
        data: StartDocumentUploadRequest,
    ):
        logger.info('Document route started: operation=create')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await start_document_upload(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    StartDocumentUploadDTO(
                        name=data.name,
                        original_filename=data.original_filename,
                        description=data.description or '',
                        content_type=data.content_type,
                    ),
                )
            logger.info('Document route completed: operation=create')
            return DocumentUploadSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '/{document_id}/uploads',
        response_model=DocumentUploadSchema,
        status_code=HTTPStatus.ACCEPTED,
    )
    async def post_document_upload(
        request: Request,
        project_id: int,
        document_id: int,
        data: ReplaceDocumentUploadRequest,
    ):
        logger.info('Document route started: operation=upload')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await start_document_replacement(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    document_id,
                    data.content_type,
                    UpdateDocumentDTO(
                        name=data.name, description=data.description
                    ),
                    original_filename=data.original_filename,
                )
            logger.info('Document route completed: operation=upload')
            return DocumentUploadSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{document_id}', response_model=DocumentSchema)
    async def put_document(
        request: Request,
        project_id: int,
        document_id: int,
        data: UpdateDocumentRequest,
    ):
        logger.info('Document route started: operation=update')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await update_document(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    document_id,
                    UpdateDocumentDTO(
                        name=data.name, description=data.description
                    ),
                )
            result = DocumentSchema.from_dto(dto)
            logger.info('Document route completed: operation=update')
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.get(
        '/{document_id}/history', response_model=DocumentEventPageSchema
    )
    async def list_document_history(
        request: Request,
        project_id: int,
        document_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
    ):
        logger.info('Document route started: operation=history')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                page = await get_document_events(
                    unit_of_work,
                    project_id,
                    user.id,
                    document_id,
                    PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                )
            result = DocumentEventPageSchema(
                items=[
                    DocumentEventSchema.from_dto(item) for item in page.items
                ],
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
            logger.info('Document route completed: operation=history')
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete('/{document_id}', status_code=HTTPStatus.NO_CONTENT)
    async def remove_document(
        request: Request,
        project_id: int,
        document_id: int,
    ):
        logger.info('Document route started: operation=delete')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                await delete_document(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    document_id,
                )
            logger.info('Document route completed: operation=delete')
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/{document_id}/file')
    async def redirect_document_file(
        request: Request,
        project_id: int,
        document_id: int,
    ):
        logger.info('Document route started: operation=file')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                url = await get_document_file_url(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    document_id,
                )
            logger.info('Document route completed: operation=file')
            return RedirectResponse(
                url=url, status_code=HTTPStatus.TEMPORARY_REDIRECT
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.get('/{document_id}/download')
    async def redirect_document_download(
        request: Request,
        project_id: int,
        document_id: int,
    ):
        logger.info('Document route started: operation=download')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                url = await download_document(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    document_id,
                )
            logger.info('Document route completed: operation=download')
            return RedirectResponse(
                url=url, status_code=HTTPStatus.TEMPORARY_REDIRECT
            )
        except ProjectException as error:
            return handle_project_error(error)

    return router


router = create_documents_router(
    create_project_unit_of_work,
    create_storage,
    create_identity_client,
)
