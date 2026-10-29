from datetime import datetime, timezone

import pytest

from project.dtos.document import (
    ApproveDocumentDTO,
    CreateDocumentDTO,
    DocumentDTO,
    UpdateDocumentDTO,
)
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    DocumentNotFoundException,
    InsufficientProjectPermissionException,
    InvalidDocumentStateException,
    ProjectNotFoundException,
)
from project.tests.fixtures.mock import make_unit_of_work
from project.use_cases.documents import (
    add_document,
    delete_document,
    download_document,
    get_document_file_url,
    get_documents,
    review_document,
    update_document,
)


def _doc(file='old-key', status=DocumentStatus.PENDING, project_id=1):
    now = datetime.now(timezone.utc)
    return DocumentDTO(4, project_id, file, 'Brief', None, status, now, now)


@pytest.mark.asyncio
async def test_get_documents_authorizes_member_and_forwards_filters(
    repos, storage
):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    expected = CursorPage([], PaginationDTO(limit=7))
    document_repo.get_documents.return_value = expected
    page = await get_documents(
        unit_of_work,
        storage,
        1,
        20,
        PaginationDTO(limit=7),
        'brief',
        DocumentStatus.PENDING,
    )
    assert page is expected
    document_repo.get_documents.assert_awaited_once_with(
        1, PaginationDTO(limit=7), 'brief', DocumentStatus.PENDING
    )


@pytest.mark.asyncio
async def test_get_document_file_url_returns_signed_url(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(file='document-key')

    result = await get_document_file_url(unit_of_work, storage, 1, 20, 4)

    assert result == 'https://rustfs.test/signed-view'
    assert storage.presigned == [('document-key', None)]


@pytest.mark.asyncio
async def test_download_document_returns_attachment_url(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(file='document-key')

    result = await download_document(unit_of_work, storage, 1, 20, 4)

    assert result == 'https://rustfs.test/signed-download'
    assert storage.presigned == [('document-key', 'Brief')]


@pytest.mark.asyncio
@pytest.mark.parametrize('document_state', ['missing', 'foreign_project'])
async def test_document_file_url_rejects_missing_or_foreign_document(
    repos, storage, document_state
):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = (
        None if document_state == 'missing' else _doc(project_id=2)
    )

    with pytest.raises(DocumentNotFoundException):
        await get_document_file_url(unit_of_work, storage, 1, 20, 4)


@pytest.mark.asyncio
async def test_get_documents_rejects_unknown_project(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    project_repo.get_project.return_value = None
    with pytest.raises(ProjectNotFoundException):
        await get_documents(unit_of_work, storage, 99, 20)


@pytest.mark.asyncio
async def test_get_documents_rejects_nonmember(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    member_repo.get_members.side_effect = None
    member_repo.get_members.return_value = CursorPage([], PaginationDTO())
    with pytest.raises(ProjectNotFoundException):
        await get_documents(unit_of_work, storage, 1, 21)


@pytest.mark.asyncio
async def test_get_documents_allows_collaborator_read(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    now = datetime.now(timezone.utc)
    guest = MemberDTO(
        3, 1, MemberRole.COLLABORATOR, MemberStatus.ACTIVE, 30, now, now
    )
    member_repo.get_members.return_value = CursorPage([guest], PaginationDTO())
    await get_documents(unit_of_work, storage, 1, 30)
    document_repo.get_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_add_document_saves_bytes_and_sets_member_pending(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.create_document.return_value = _doc()
    result = await add_document(
        unit_of_work,
        storage,
        1,
        20,
        CreateDocumentDTO('ignored', 'Brief', 'Description'),
        b'body',
        'application/pdf',
    )
    key = document_repo.create_document.await_args.args[1]
    assert key.startswith('projects/1/documents/')
    assert storage.files[key] == b'body'
    assert storage.saved == [(key, b'body', 'application/pdf')]
    document_repo.create_document.assert_awaited_once_with(
        1, key, 'Brief', 'Description', DocumentStatus.PENDING
    )
    assert result.file == 'old-key'


@pytest.mark.asyncio
async def test_add_document_publishes_for_owner(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.create_document.return_value = _doc(
        status=DocumentStatus.PUBLISHED
    )
    await add_document(
        unit_of_work,
        storage,
        1,
        10,
        CreateDocumentDTO('', 'Brief', ''),
        b'body',
    )
    assert (
        document_repo.create_document.await_args.args[-1]
        is DocumentStatus.PUBLISHED
    )


@pytest.mark.asyncio
async def test_add_document_cleans_storage_if_repository_fails(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.create_document.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await add_document(
            unit_of_work,
            storage,
            1,
            20,
            CreateDocumentDTO('', 'Brief', ''),
            b'body',
        )
    assert len(storage.deleted) == 1
    assert storage.files == {}


@pytest.mark.asyncio
async def test_update_document_replaces_file_after_update(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    document_repo.update_document.return_value = _doc(file='new-key')
    result = await update_document(
        unit_of_work,
        storage,
        1,
        10,
        4,
        UpdateDocumentDTO(name='Updated'),
        b'new bytes',
    )
    new_key = document_repo.update_document.await_args.kwargs['file']
    assert result.file == 'new-key'
    assert storage.files[new_key] == b'new bytes'
    assert storage.deleted == ['old-key']


@pytest.mark.asyncio
async def test_update_document_without_file_preserves_storage(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    document_repo.update_document.return_value = _doc()
    await update_document(
        unit_of_work,
        storage,
        1,
        10,
        4,
        UpdateDocumentDTO(name='Updated'),
    )
    document_repo.update_document.assert_awaited_once_with(
        4, file=None, name='Updated', description=None
    )
    assert storage.deleted == []


@pytest.mark.asyncio
async def test_update_document_rejects_wrong_project(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(project_id=2)
    with pytest.raises(DocumentNotFoundException):
        await update_document(
            unit_of_work,
            storage,
            1,
            10,
            4,
            UpdateDocumentDTO(),
        )


@pytest.mark.asyncio
async def test_update_document_rejects_role_without_update_permission(
    repos, storage
):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    now = datetime.now(timezone.utc)
    collaborator = MemberDTO(
        3, 1, MemberRole.COLLABORATOR, MemberStatus.ACTIVE, 30, now, now
    )
    member_repo.get_members.return_value = CursorPage(
        [collaborator], PaginationDTO()
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await update_document(
            unit_of_work,
            storage,
            1,
            30,
            4,
            UpdateDocumentDTO(),
        )
    document_repo.get_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_document_cleans_new_file_when_record_disappears(
    repos, storage
):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    document_repo.update_document.return_value = None
    with pytest.raises(DocumentNotFoundException):
        await update_document(
            unit_of_work,
            storage,
            1,
            10,
            4,
            UpdateDocumentDTO(),
            b'replacement',
        )
    assert storage.deleted == [
        document_repo.update_document.await_args.kwargs['file']
    ]
    assert storage.files == {}


@pytest.mark.asyncio
async def test_update_document_does_not_clean_storage_without_replacement(
    repos, storage
):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    document_repo.update_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await update_document(
            unit_of_work,
            storage,
            1,
            10,
            4,
            UpdateDocumentDTO(name='Updated'),
        )

    assert storage.deleted == []


@pytest.mark.asyncio
async def test_delete_document_removes_record_and_file(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    await delete_document(unit_of_work, storage, 1, 20, 4)
    document_repo.delete_document.assert_awaited_once_with(4)
    assert storage.deleted == ['old-key']


@pytest.mark.asyncio
async def test_delete_document_rejects_missing_document(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = None
    with pytest.raises(DocumentNotFoundException):
        await delete_document(unit_of_work, storage, 1, 20, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('accept', 'status'),
    [(True, DocumentStatus.PUBLISHED), (False, DocumentStatus.DRAFT)],
)
async def test_review_document_changes_status(repos, accept, status):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    document_repo.update_document.return_value = _doc(status=status)
    result = await review_document(
        unit_of_work,
        1,
        10,
        4,
        ApproveDocumentDTO(accept),
    )
    assert result.status is status
    document_repo.update_document.assert_awaited_once_with(4, status=status)


@pytest.mark.asyncio
async def test_review_document_rejects_nonpending_document(repos):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(status=DocumentStatus.DRAFT)
    with pytest.raises(InvalidDocumentStateException):
        await review_document(
            unit_of_work,
            1,
            10,
            4,
            ApproveDocumentDTO(True),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize('document', [None, _doc(project_id=2)])
async def test_review_document_rejects_missing_or_wrong_project(
    repos, document
):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = document
    with pytest.raises(DocumentNotFoundException):
        await review_document(
            unit_of_work,
            1,
            10,
            4,
            ApproveDocumentDTO(True),
        )
    document_repo.update_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_document_rejects_missing_record_after_update(repos):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc()
    document_repo.update_document.return_value = None
    with pytest.raises(DocumentNotFoundException):
        await review_document(
            unit_of_work,
            1,
            10,
            4,
            ApproveDocumentDTO(False),
        )
