# ruff: noqa: PLR0913, PLR0917
from uuid import uuid4

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
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.storage import IStorage


async def _get_member(
    member_repo: IMemberRepository, project_id: int, user_id: int
):
    members = await member_repo.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    if not members.items:
        raise ProjectNotFoundException(project_id)
    return members.items[0]


async def _authorize(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    project_id: int,
    user_id: int,
    permission: ProjectPermission,
):
    if await project_repo.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    member = await _get_member(member_repo, project_id, user_id)
    if not has_permission(member.role, permission):
        raise InsufficientProjectPermissionException(permission)
    return member


def _new_storage_key(project_id: int) -> str:
    return f'projects/{project_id}/documents/{uuid4().hex}'


async def get_documents(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    document_repo: IDocumentRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
    name: str | None = None,
    status: DocumentStatus | None = None,
) -> CursorPage[DocumentDTO]:
    await _authorize(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_READ,
    )
    del storage  # Listing returns metadata; file contents remain in storage.
    return await document_repo.get_documents(
        project_id, pagination, name, status
    )


async def add_document(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    document_repo: IDocumentRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: CreateDocumentDTO,
    content: bytes,
) -> DocumentDTO:
    member = await _authorize(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_CREATE,
    )
    key = _new_storage_key(project_id)
    storage.save(key, content)
    status = (
        DocumentStatus.PUBLISHED
        if has_permission(member.role, ProjectPermission.DOCUMENT_APPROVE)
        else DocumentStatus.PENDING
    )
    try:
        return await document_repo.create_document(
            project_id, key, data.name, data.description, status
        )
    except Exception:
        storage.delete(key)
        raise


async def update_document(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    document_repo: IDocumentRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
    data: UpdateDocumentDTO,
    content: bytes | None = None,
) -> DocumentDTO:
    await _authorize(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_UPDATE,
    )
    document = await document_repo.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    new_key = _new_storage_key(project_id) if content is not None else None
    if new_key is not None:
        storage.save(new_key, content)
    try:
        updated = await document_repo.update_document(
            document_id,
            file=new_key,
            name=data.name,
            description=data.description,
        )
        if updated is None:
            raise DocumentNotFoundException(document_id)
    except Exception:
        if new_key is not None:
            storage.delete(new_key)
        raise
    if new_key is not None:
        storage.delete(document.file)
    return updated


async def delete_document(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    document_repo: IDocumentRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    document_id: int,
) -> None:
    await _authorize(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_DELETE,
    )
    document = await document_repo.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    await document_repo.delete_document(document_id)
    storage.delete(document.file)


async def review_document(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    document_repo: IDocumentRepository,
    project_id: int,
    user_id: int,
    document_id: int,
    data: ApproveDocumentDTO,
) -> DocumentDTO:
    await _authorize(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.DOCUMENT_APPROVE,
    )
    document = await document_repo.get_document(document_id)
    if document is None or document.project_id != project_id:
        raise DocumentNotFoundException(document_id)
    if document.status is not DocumentStatus.PENDING:
        raise InvalidDocumentStateException(document_id, document.status)
    updated = await document_repo.update_document(
        document_id,
        status=(
            DocumentStatus.PUBLISHED if data.accept else DocumentStatus.DRAFT
        ),
    )
    if updated is None:
        raise DocumentNotFoundException(document_id)
    return updated
