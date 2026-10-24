# ruff: noqa: PLR0913, PLR0917
from collections.abc import Callable
from http import HTTPStatus

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import Response

from core.logs import get_logger
from project.clients.client_user import IUserClient
from project.dtos.document import (
    CreateDocumentDTO,
    UpdateDocumentDTO,
)
from project.dtos.page import PaginationDTO
from project.entities.document import DocumentStatus
from project.exceptions import (
    ProjectException,
    ProjectUserAuthenticationException,
)
from project.handlers.errors import handle_project_error
from project.schemas.document import DocumentPageSchema, DocumentSchema
from project.storage import IStorage
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.documents import (
    add_document,
    delete_document,
    get_documents,
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
        '', response_model=DocumentSchema, status_code=HTTPStatus.CREATED
    )
    async def post_document(
        request: Request,
        project_id: int,
        name: str = Form(...),
        description: str | None = Form(default=None),
        file: UploadFile = File(...),
    ):
        logger.info('Document route started: operation=create')
        try:
            user = await resolve_current_user(request.cookies)
            async with unit_of_work_factory() as unit_of_work:
                dto = await add_document(
                    unit_of_work,
                    storage_factory(),
                    project_id,
                    user.id,
                    CreateDocumentDTO(
                        file='', name=name, description=description or ''
                    ),
                    await file.read(),
                )
            result = DocumentSchema.from_dto(dto)
            logger.info('Document route completed: operation=create')
            return result
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{document_id}', response_model=DocumentSchema)
    async def put_document(
        request: Request,
        project_id: int,
        document_id: int,
        name: str | None = Form(default=None),
        description: str | None = Form(default=None),
        file: UploadFile | None = File(default=None),
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
                    UpdateDocumentDTO(name=name, description=description),
                    await file.read() if file is not None else None,
                )
            result = DocumentSchema.from_dto(dto)
            logger.info('Document route completed: operation=update')
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

    return router
