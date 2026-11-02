# ruff: noqa: PLR0913, PLR0917
from datetime import UTC, datetime, timedelta
from secrets import token_hex

from infra.logs import get_logger
from infra.settings import get_settings
from project.dtos.document import (
    ApproveDocumentDTO,
    CreateDocumentDTO,
    DocumentDTO,
    DocumentUploadCompletionDTO,
    DocumentUploadDTO,
    StartDocumentUploadDTO,
    UpdateDocumentDTO,
)
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
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
from project.use_cases.resource_events import (
    get_resource_events,
    record_resource_event,
)
from project.use_cases.upload_intents import (
    complete_document_upload as complete_document_upload_intent,
)
from project.use_cases.upload_intents import create_upload_intent
from project.utils.files import build_download_filename, file_extension

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
    return f'projects/{project_id}/documents/{token_hex(16)}'


def _new_upload_key(project_id: int) -> str:
    return f'uploads/projects/{project_id}/documents/{token_hex(16)}'


def _document_status_after_upload(member) -> DocumentStatus:
    return (
        DocumentStatus.PUBLISHED
        if has_permission(member.role, ProjectPermission.DOCUMENT_APPROVE)
        else DocumentStatus.PENDING
    )


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


def _document_filename(document: DocumentDTO) -> str:
    return build_download_filename(
        document.name,
        document.file_extension,
        fallback=f'document-{document.id}',
    )


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
    if document.file is None:
        raise InvalidDocumentStateException(document.id, document.status)
    download_options = {
        'download_filename': _document_filename(document),
        'disposition': 'inline',
    }
    if document.content_type is not None:
        download_options['content_type'] = document.content_type
    return await storage.get_presigned_url(document.file, **download_options)


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
    if document.file is None:
        raise InvalidDocumentStateException(document.id, document.status)
    filename = _document_filename(document)
    download_options = {'download_filename': filename}
    if document.content_type is not None:
        download_options['content_type'] = document.content_type
    return await storage.get_presigned_url(document.file, **download_options)


async def start_document_upload(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: StartDocumentUploadDTO,
) -> DocumentUploadDTO:
    member = await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_CREATE,
    )
    content_type = data.content_type or 'application/octet-stream'
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS
    )
    key = _new_upload_key(project_id)
    final_key = _new_storage_key(project_id)
    upload_url = await storage.generate_presigned_put_url(
        key,
        content_type,
        settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS,
    )
    target_status = _document_status_after_upload(member)
    document = await uow.document_repository.create_document(
        project_id=project_id,
        created_by_member_id=member.id,
        file=None,
        name=data.name,
        description=data.description or None,
        status=DocumentStatus.UPLOADING,
    )
    extension = file_extension(
        data.original_filename or data.name, content_type
    )
    await create_upload_intent(
        uow,
        project_id,
        document_id=document.id,
        object_key=key,
        final_file_key=final_key,
        started_by_member_id=member.id,
        target_status=target_status.value,
        file_extension=extension,
        content_type=content_type,
        expires_at=expires_at,
    )
    await record_resource_event(
        uow,
        project_id,
        'document',
        document.id,
        member.id,
        'resource_created',
        {'name': document.name, 'description': document.description},
    )
    await record_resource_event(
        uow,
        project_id,
        'document',
        document.id,
        member.id,
        'upload_started',
        {'object_key': key, 'expires_at': expires_at.isoformat()},
    )
    await uow.commit()
    return DocumentUploadDTO(
        document=document,
        upload_url=upload_url,
        expires_at=expires_at,
        required_headers={'Content-Type': content_type},
    )


async def start_document_replacement(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
    content_type: str = 'application/octet-stream',
    data: UpdateDocumentDTO = UpdateDocumentDTO(),
    original_filename: str | None = None,
) -> DocumentUploadDTO:
    member = await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_UPDATE,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    if document.status is DocumentStatus.UPLOADING:
        raise InvalidDocumentStateException(document.id, document.status)
    target_status = (
        _document_status_after_upload(member)
        if document.status is DocumentStatus.FAILED
        else document.status
    )

    content_type = content_type or 'application/octet-stream'
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(
        seconds=settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS
    )
    key = _new_upload_key(project_id)
    final_key = _new_storage_key(project_id)
    upload_url = await storage.generate_presigned_put_url(
        key,
        content_type,
        settings.RUSTFS_PRESIGNED_URL_TTL_SECONDS,
    )
    updated = await uow.document_repository.update_document(
        document_id,
        name=data.name,
        description=data.description,
        status=DocumentStatus.UPLOADING,
    )
    if updated is None:
        raise DocumentNotFoundException(document_id)
    extension = file_extension(
        original_filename or data.name or document.name, content_type
    )
    await create_upload_intent(
        uow,
        project_id,
        document_id=document_id,
        object_key=key,
        final_file_key=final_key,
        started_by_member_id=member.id,
        target_status=target_status.value,
        file_extension=extension,
        content_type=content_type,
        expires_at=expires_at,
        previous_file_key=document.file,
    )
    await record_resource_event(
        uow,
        project_id,
        'document',
        document_id,
        member.id,
        'upload_started',
        {'object_key': key, 'expires_at': expires_at.isoformat()},
    )
    changes = {}
    if data.name is not None and data.name != document.name:
        changes['name'] = {'old': document.name, 'new': data.name}
    if (
        data.description is not None
        and data.description != document.description
    ):
        changes['description'] = {
            'old': document.description,
            'new': data.description,
        }
    if changes:
        await record_resource_event(
            uow,
            project_id,
            'document',
            document_id,
            member.id,
            'metadata_changed',
            {'changes': changes},
        )
    await uow.commit()
    return DocumentUploadDTO(
        document=updated,
        upload_url=upload_url,
        expires_at=expires_at,
        required_headers={'Content-Type': content_type},
    )


async def complete_document_upload(
    uow: IProjectUnitOfWork, object_key: str
) -> DocumentUploadCompletionDTO:
    return await complete_document_upload_intent(uow, object_key)


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
    status = _document_status_after_upload(member)
    try:
        document = await uow.document_repository.create_document(
            project_id=project_id,
            created_by_member_id=member.id,
            file=key,
            name=data.name,
            description=data.description,
            status=status,
            file_extension=file_extension(data.name, content_type),
            content_type=content_type,
        )
        await record_resource_event(
            uow,
            project_id,
            'document',
            document.id,
            member.id,
            'resource_created',
            {'name': document.name, 'description': document.description},
        )
        await record_resource_event(
            uow,
            project_id,
            'document',
            document.id,
            member.id,
            'file_changed',
            {'previous_file_key': None, 'file_key': key},
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
    member = await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_UPDATE,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    if document.status is DocumentStatus.UPLOADING:
        raise InvalidDocumentStateException(document.id, document.status)
    new_key = _new_storage_key(project_id) if content is not None else None
    if new_key is not None:
        await storage.save(new_key, content, content_type)
    try:
        file_metadata = (
            {
                'file_extension': file_extension(
                    data.name or document.name, content_type
                ),
                'content_type': content_type,
            }
            if content is not None
            else {}
        )
        updated = await uow.document_repository.update_document(
            document_id,
            file=new_key,
            name=data.name,
            description=data.description,
            **file_metadata,
        )
        if updated is None:
            raise DocumentNotFoundException(document_id)
        changes = {}
        if data.name is not None and data.name != document.name:
            changes['name'] = {'old': document.name, 'new': data.name}
        if (
            data.description is not None
            and data.description != document.description
        ):
            changes['description'] = {
                'old': document.description,
                'new': data.description,
            }
        if content is not None:
            await record_resource_event(
                uow,
                project_id,
                'document',
                document_id,
                member.id,
                'file_changed',
                {
                    'previous_file_key': document.file,
                    'file_key': new_key,
                    'file_extension': updated.file_extension,
                    'content_type': updated.content_type,
                },
            )
        if data.name is not None or data.description is not None:
            if changes:
                await record_resource_event(
                    uow,
                    project_id,
                    'document',
                    document_id,
                    member.id,
                    'metadata_changed',
                    {'changes': changes},
                )
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
    if new_key is not None and document.file is not None:
        await storage.delete(document.file)
    return updated


async def delete_document(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
) -> None:
    member = await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_DELETE,
    )
    document = await uow.document_repository.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    if document.status is DocumentStatus.UPLOADING:
        raise InvalidDocumentStateException(document.id, document.status)
    await record_resource_event(
        uow,
        project_id,
        'document',
        document_id,
        member.id,
        'resource_deleted',
        {'name': document.name, 'file_key': document.file},
    )
    await uow.document_repository.delete_document(document_id)
    await uow.commit()
    if document.file is not None:
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
    member = await _authorize(
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
    await record_resource_event(
        uow,
        project_id,
        'document',
        document_id,
        member.id,
        'status_changed',
        {
            'old': document.status.value,
            'new': updated.status.value,
        },
    )
    await uow.commit()
    logger.info(
        'Document review completed: project_id=%s document_id=%s accepted=%s',
        project_id,
        document_id,
        data.accept,
    )
    return updated


async def get_document_events(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    document_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ResourceEventDTO]:
    await _authorize(
        uow,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_READ,
    )
    return await get_resource_events(
        uow,
        project_id,
        'document',
        document_id,
        pagination,
    )
