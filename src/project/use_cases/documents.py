# ruff: noqa: PLR0913, PLR0917
from uuid import uuid4

from infra.logs import get_logger
from project.dtos.document import (
    ApproveDocumentDTO,
    CreateDocumentDTO,
    DocumentDTO,
    UpdateDocumentDTO,
)
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.document import DocumentStatus
from project.entities.member import MemberStatus
from project.exceptions import (
    DocumentNotFoundException,
    InsufficientProjectPermissionException,
    InvalidDocumentStateException,
    ProjectNotFoundException,
)
from project.permissions import ProjectPermission, has_permission
from project.storage import IStorage
from project.unit_of_work import IProjectUnitOfWork

logger = get_logger(__name__)


async def _get_member(uow: IProjectUnitOfWork, project_id: int, user_id: int):
    members = await uow.member_repository.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    if not members.items:
        raise ProjectNotFoundException(project_id)
    return members.items[0]


async def _authorize(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    permission: ProjectPermission,
):
    if await uow.project_repository.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    member = await _get_member(uow, project_id, user_id)
    if not has_permission(member.role, permission):
        raise InsufficientProjectPermissionException(permission)
    return member


def _new_storage_key(project_id: int) -> str:
    return f'projects/{project_id}/documents/{uuid4().hex}'


async def get_documents(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
    name: str | None = None,
    status: DocumentStatus | None = None,
) -> CursorPage[DocumentDTO]:
    await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_READ,
    )
    del storage  # Listing returns metadata; file contents remain in storage.
    page = await uow.document_repository.get_documents(
        project_id, pagination, name, status
    )
    logger.debug(
        'Documents loaded: project_id=%s count=%s', project_id, len(page.items)
    )
    return page


async def _get_document_for_read(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
) -> DocumentDTO:
    await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_READ,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    return document


async def get_document_file_url(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
) -> str:
    document = await _get_document_for_read(
        uow, project_id, user_id, document_id
    )
    return await storage.get_presigned_url(document.file)


async def download_document(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
) -> str:
    document = await _get_document_for_read(
        uow, project_id, user_id, document_id
    )
    filename = (
        document.name.replace('/', '_')
        .replace('\\', '_')
        .replace('\r', '')
        .replace('\n', '')
        or f'document-{document.id}'
    )
    return await storage.get_presigned_url(
        document.file, download_filename=filename
    )


async def add_document(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: CreateDocumentDTO,
    content: bytes,
    content_type: str | None = None,
) -> DocumentDTO:
    member = await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_CREATE,
    )
    key = _new_storage_key(project_id)
    await storage.save(key, content, content_type)
    status = (
        DocumentStatus.PUBLISHED
        if has_permission(member.role, ProjectPermission.DOCUMENT_APPROVE)
        else DocumentStatus.PENDING
    )
    try:
        document = await uow.document_repository.create_document(
            project_id, key, data.name, data.description, status
        )
        await uow.commit()
        logger.info('Document created: project_id=%s', project_id)
        return document
    except Exception:
        logger.exception('Document creation failed: project_id=%s', project_id)
        await storage.delete(key)
        raise


async def update_document(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
    data: UpdateDocumentDTO,
    content: bytes | None = None,
    content_type: str | None = None,
) -> DocumentDTO:
    await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_UPDATE,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    new_key = _new_storage_key(project_id) if content is not None else None
    if new_key is not None:
        await storage.save(new_key, content, content_type)
    try:
        updated = await uow.document_repository.update_document(
            document_id,
            file=new_key,
            name=data.name,
            description=data.description,
        )
        if updated is None:
            raise DocumentNotFoundException(document_id)
        await uow.commit()
        logger.info(
            'Document updated: project_id=%s document_id=%s',
            project_id,
            document_id,
        )
    except Exception:
        logger.exception(
            'Document update failed: project_id=%s document_id=%s',
            project_id,
            document_id,
        )
        if new_key is not None:
            await storage.delete(new_key)
        raise
    if new_key is not None:
        await storage.delete(document.file)
    return updated


async def delete_document(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
) -> None:
    await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_DELETE,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    await uow.document_repository.delete_document(document_id)
    await uow.commit()
    await storage.delete(document.file)
    logger.info(
        'Document deleted: project_id=%s document_id=%s',
        project_id,
        document_id,
    )


async def review_document(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
    data: ApproveDocumentDTO,
) -> DocumentDTO:
    await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_APPROVE,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    if document.status is not DocumentStatus.PENDING:
        raise InvalidDocumentStateException(document_id, document.status)
    updated = await uow.document_repository.update_document(
        document_id,
        status=(
            DocumentStatus.PUBLISHED if data.accept else DocumentStatus.DRAFT
        ),
    )
    if updated is None:
        raise DocumentNotFoundException(document_id)
    await uow.commit()
    logger.info(
        'Document review completed: project_id=%s document_id=%s accepted=%s',
        project_id,
        document_id,
        data.accept,
    )
    return updated
