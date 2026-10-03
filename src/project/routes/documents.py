# ruff: noqa: PLR0913, PLR0917
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.schemas.document import DocumentPageSchema, DocumentSchema
from project.storage import IStorage
from project.use_cases.documents import (
    add_document,
    delete_document,
    get_documents,
    update_document,
)
from project.utils.pagination import decode_cursor, encode_cursor


def create_documents_router(
    project_repository_factory: Callable[[], Awaitable[IProjectRepository]],
    member_repository_factory: Callable[[], Awaitable[IMemberRepository]],
    document_repository_factory: Callable[[], Awaitable[IDocumentRepository]],
    storage_factory: Callable[[], IStorage],
    user_client_factory: Callable[[], IUserClient],
) -> APIRouter:
    router = APIRouter(
        prefix='/projects/{project_id}/documents', tags=['documents']
    )
    bearer = HTTPBearer(auto_error=False)

    async def current_user(
        credentials: HTTPAuthorizationCredentials | None,
    ):
        if credentials is None:
            raise ProjectUserAuthenticationException()
        return await user_client_factory().get_current_user(
            credentials.credentials
        )

    @router.get('', response_model=DocumentPageSchema)
    async def list_documents(
        project_id: int,
        cursor: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
        name: str | None = Query(default=None),
        status: DocumentStatus | None = Query(default=None),
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            page = await get_documents(
                await project_repository_factory(),
                await member_repository_factory(),
                await document_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                PaginationDTO(cursor=decode_cursor(cursor), limit=limit),
                name,
                status,
            )
            return DocumentPageSchema(
                items=[DocumentSchema.from_dto(item) for item in page.items],
                limit=page.pagination.limit,
                more=page.pagination.more,
                cursor=encode_cursor(page.pagination.cursor),
            )
        except ProjectException as error:
            return handle_project_error(error)

    @router.post(
        '', response_model=DocumentSchema, status_code=HTTPStatus.CREATED
    )
    async def post_document(
        project_id: int,
        name: str = Form(...),
        description: str | None = Form(default=None),
        file: UploadFile = File(...),
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            dto = await add_document(
                await project_repository_factory(),
                await member_repository_factory(),
                await document_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                CreateDocumentDTO(
                    file='', name=name, description=description or ''
                ),
                await file.read(),
            )
            return DocumentSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.put('/{document_id}', response_model=DocumentSchema)
    async def put_document(
        project_id: int,
        document_id: int,
        name: str | None = Form(default=None),
        description: str | None = Form(default=None),
        file: UploadFile | None = File(default=None),
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            dto = await update_document(
                await project_repository_factory(),
                await member_repository_factory(),
                await document_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                document_id,
                UpdateDocumentDTO(name=name, description=description),
                await file.read() if file is not None else None,
            )
            return DocumentSchema.from_dto(dto)
        except ProjectException as error:
            return handle_project_error(error)

    @router.delete('/{document_id}', status_code=HTTPStatus.NO_CONTENT)
    async def remove_document(
        project_id: int,
        document_id: int,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ):
        try:
            user = await current_user(credentials)
            await delete_document(
                await project_repository_factory(),
                await member_repository_factory(),
                await document_repository_factory(),
                storage_factory(),
                project_id,
                user.id,
                document_id,
            )
            return Response(status_code=HTTPStatus.NO_CONTENT)
        except ProjectException as error:
            return handle_project_error(error)

    return router
