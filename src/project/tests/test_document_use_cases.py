from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from project.dtos.document import (
    ApproveDocumentDTO,
    CreateDocumentDTO,
    DocumentDTO,
    StartDocumentUploadDTO,
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
from project.tests.fixtures.document_uploads import (
    make_document_upload_intent,
)
from project.tests.fixtures.mock import make_unit_of_work
from project.use_cases.documents import (
    add_document,
    complete_document_upload,
    delete_document,
    download_document,
    get_document_events,
    get_document_file_url,
    get_documents,
    review_document,
    start_document_replacement,
    start_document_upload,
    update_document,
)

EXPECTED_UPLOAD_START_EVENTS = 2
pytest_plugins = ('project.tests.fixtures.document_uploads',)


def _doc(file='old-key', status=DocumentStatus.PENDING, project_id=1, **extra):
    now = datetime.now(timezone.utc)
    values = {
        'id': 4,
        'project_id': project_id,
        'created_by_member_id': 2,
        'file': file,
        'name': 'Brief',
        'description': None,
        'status': status,
        'created_at': now,
        'updated_at': now,
    }
    values.update(extra)
    return DocumentDTO(**values)


def _upload_settings(monkeypatch, ttl=900):
    monkeypatch.setattr(
        'project.use_cases.documents.get_settings',
        lambda: SimpleNamespace(RUSTFS_PRESIGNED_URL_TTL_SECONDS=ttl),
    )


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
    document_repo.get_document.return_value = _doc(
        file='document-key',
        name='texto',
        file_extension='md',
        content_type='text/markdown',
    )

    result = await get_document_file_url(unit_of_work, storage, 1, 20, 4)

    assert result == 'https://rustfs.test/signed-view'
    assert storage.presigned == [
        ('document-key', 'texto.md', 'text/markdown', 'inline')
    ]


@pytest.mark.asyncio
async def test_document_file_urls_reject_uploading_document(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(
        file=None, status=DocumentStatus.UPLOADING
    )

    with pytest.raises(InvalidDocumentStateException):
        await get_document_file_url(unit_of_work, storage, 1, 20, 4)

    assert storage.presigned == []


@pytest.mark.asyncio
async def test_download_rejects_document_without_file(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(file=None)

    with pytest.raises(InvalidDocumentStateException):
        await download_document(unit_of_work, storage, 1, 20, 4)


@pytest.mark.asyncio
async def test_download_document_returns_attachment_url(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(
        file='document-key',
        name='texto',
        file_extension='md',
        content_type='text/markdown',
    )

    result = await download_document(unit_of_work, storage, 1, 20, 4)

    assert result == 'https://rustfs.test/signed-download'
    assert storage.presigned == [
        ('document-key', 'texto.md', 'text/markdown', 'attachment')
    ]


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
        CreateDocumentDTO('Brief', 'Description'),
        b'body',
        'application/pdf',
    )
    key = document_repo.create_document.await_args.kwargs['file']
    assert key.startswith('projects/1/documents/')
    assert storage.files[key] == b'body'
    assert storage.saved == [(key, b'body', 'application/pdf')]
    document_repo.create_document.assert_awaited_once_with(
        project_id=1,
        created_by_member_id=2,
        file=key,
        name='Brief',
        description='Description',
        status=DocumentStatus.PENDING,
        file_extension='pdf',
        content_type='application/pdf',
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
        CreateDocumentDTO('Brief', ''),
        b'body',
    )
    assert (
        document_repo.create_document.await_args.kwargs['status']
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
            CreateDocumentDTO('Brief', ''),
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
async def test_download_sanitizes_filename_and_uses_fallback(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = DocumentDTO(
        4,
        1,
        2,
        'key',
        '\r\n',
        None,
        DocumentStatus.PUBLISHED,
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
    )

    await download_document(unit_of_work, storage, 1, 20, 4)

    assert storage.presigned == [('key', 'document-4', None, 'attachment')]


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
async def test_update_document_rejects_uploading_document(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(
        file=None, status=DocumentStatus.UPLOADING
    )

    with pytest.raises(InvalidDocumentStateException):
        await update_document(
            unit_of_work, storage, 1, 10, 4, UpdateDocumentDTO(name='New')
        )

    document_repo.update_document.assert_not_awaited()


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
async def test_delete_document_rejects_uploading_document(repos, storage):
    project_repo, member_repo, document_repo = repos
    unit_of_work = make_unit_of_work(
        project_repo, member_repo, document_repo=document_repo
    )
    document_repo.get_document.return_value = _doc(
        file=None, status=DocumentStatus.UPLOADING
    )

    with pytest.raises(InvalidDocumentStateException):
        await delete_document(unit_of_work, storage, 1, 20, 4)

    document_repo.delete_document.assert_not_awaited()


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
    event_call = unit_of_work.resource_event_repository.create_event.await_args
    assert event_call.args[3] == 1
    assert event_call.args[4] == 'status_changed'
    assert event_call.args[5] == {
        'old': DocumentStatus.PENDING.value,
        'new': status.value,
    }


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


@pytest.mark.asyncio
async def test_start_document_upload_returns_signed_url_and_records_creator(
    document_upload_dependencies, monkeypatch
):
    deps = document_upload_dependencies
    _upload_settings(monkeypatch, ttl=300)

    result = await start_document_upload(
        deps.uow,
        deps.storage,
        2,
        7,
        StartDocumentUploadDTO(
            'Brief', 'Overview', 'application/pdf', 'texto.md'
        ),
    )

    assert result.upload_url == 'https://rustfs.test/signed-put'
    assert result.document.status is DocumentStatus.UPLOADING
    assert result.document.file is None
    assert result.required_headers == {'Content-Type': 'application/pdf'}
    assert deps.document_repo.create_document.await_args.kwargs == {
        'project_id': 2,
        'created_by_member_id': deps.member.id,
        'file': None,
        'name': 'Brief',
        'description': 'Overview',
        'status': DocumentStatus.UPLOADING,
    }
    deps.storage.generate_presigned_put_url.assert_awaited_once()
    intent_args = deps.upload_intent_repo.create_upload_intent.await_args
    assert intent_args.args == (2,)
    assert intent_args.kwargs['document_id'] == deps.document.id
    assert intent_args.kwargs['started_by_member_id'] == deps.member.id
    assert intent_args.kwargs['target_status'] == DocumentStatus.PUBLISHED.value
    assert intent_args.kwargs['file_extension'] == 'md'
    assert intent_args.kwargs['content_type'] == 'application/pdf'
    assert (
        len(deps.resource_event_repo.create_event.await_args_list)
        == EXPECTED_UPLOAD_START_EVENTS
    )
    assert all(
        call.args[3] == deps.member.id
        for call in deps.resource_event_repo.create_event.await_args_list
    )
    assert deps.uow.commit.await_count == 1


@pytest.mark.asyncio
async def test_start_document_upload_denial_does_not_sign_or_create(
    document_upload_dependencies, monkeypatch
):
    deps = document_upload_dependencies
    _upload_settings(monkeypatch)
    deps.member_repo.get_members.return_value = CursorPage([], PaginationDTO())

    with pytest.raises(ProjectNotFoundException):
        await start_document_upload(
            deps.uow, deps.storage, 2, 7, StartDocumentUploadDTO('Brief')
        )

    deps.storage.generate_presigned_put_url.assert_not_awaited()
    deps.document_repo.create_document.assert_not_awaited()
    deps.upload_intent_repo.create_upload_intent.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_document_replacement_tracks_previous_file_and_metadata(
    document_upload_dependencies, monkeypatch
):
    deps = document_upload_dependencies
    _upload_settings(monkeypatch)

    result = await start_document_replacement(
        deps.uow,
        deps.storage,
        2,
        7,
        deps.document.id,
        'image/png',
        UpdateDocumentDTO(name='New brief', description='New overview'),
    )

    assert result.document.status is DocumentStatus.UPLOADING
    args = deps.upload_intent_repo.create_upload_intent.await_args.kwargs
    assert args['previous_file_key'] == deps.document.file
    assert args['started_by_member_id'] == deps.member.id
    assert (
        deps.resource_event_repo.create_event.await_count
        == EXPECTED_UPLOAD_START_EVENTS
    )
    assert any(
        call.args[4] == 'metadata_changed'
        for call in deps.resource_event_repo.create_event.await_args_list
    )


@pytest.mark.asyncio
async def test_start_replacement_rejects_document_already_uploading(
    document_upload_dependencies, monkeypatch
):
    deps = document_upload_dependencies
    _upload_settings(monkeypatch)

    deps.document_repo.get_document.return_value = replace(
        deps.document, status=DocumentStatus.UPLOADING
    )

    with pytest.raises(InvalidDocumentStateException):
        await start_document_replacement(
            deps.uow, deps.storage, 2, 7, deps.document.id
        )

    deps.storage.generate_presigned_put_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_replacement_rejects_missing_document(
    document_upload_dependencies, monkeypatch
):
    deps = document_upload_dependencies
    _upload_settings(monkeypatch)
    deps.document_repo.get_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await start_document_replacement(
            deps.uow, deps.storage, 2, 7, deps.document.id
        )

    deps.storage.generate_presigned_put_url.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_replacement_rejects_repository_disappearance(
    document_upload_dependencies, monkeypatch
):
    deps = document_upload_dependencies
    _upload_settings(monkeypatch)
    deps.document_repo.update_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await start_document_replacement(
            deps.uow, deps.storage, 2, 7, deps.document.id
        )

    deps.upload_intent_repo.create_upload_intent.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_document_upload_promotes_staging_key_and_records_event(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    intent = make_document_upload_intent(deps, previous_file_key='old-key')

    deps.document_repo.get_document.return_value = replace(
        deps.document, file=None, status=DocumentStatus.UPLOADING
    )
    deps.document_repo.update_document.return_value = replace(
        deps.document, status=DocumentStatus.PUBLISHED
    )
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent

    result = await complete_document_upload(deps.uow, intent.object_key)

    assert result.document_id == deps.document.id
    assert result.obsolete_file_key == 'old-key'
    deps.document_repo.update_document.assert_awaited_once_with(
        deps.document.id,
        file=intent.final_file_key,
        status=DocumentStatus.PUBLISHED,
        file_extension=intent.file_extension,
        content_type=intent.content_type,
    )
    event_args = deps.resource_event_repo.create_event.await_args
    assert event_args.args[3:5] == (deps.member.id, 'file_changed')
    assert event_args.kwargs['idempotency_key'] == intent.object_key
    deps.upload_intent_repo.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )


@pytest.mark.asyncio
async def test_complete_document_upload_is_idempotent_after_event_exists(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = None
    prior_event = SimpleNamespace(
        event_type='file_changed',
        resource_id=deps.document.id,
        data={'obsolete_file_key': 'old-key'},
    )
    deps.resource_event_repo.get_by_idempotency_key.return_value = prior_event

    result = await complete_document_upload(deps.uow, 'staging/key')

    assert result.document_id == deps.document.id
    assert result.already_completed is True
    assert result.obsolete_file_key == 'old-key'
    deps.upload_intent_repo.get_by_object_key_for_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_unknown_document_upload_is_ignored(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = None

    result = await complete_document_upload(deps.uow, 'unknown/key')

    assert result.ignored is True
    assert result.document_id is None
    deps.document_repo.update_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_upload_returns_completion_event_without_intent(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    prior_event = SimpleNamespace(
        event_type='file_changed',
        resource_id=deps.document.id,
        data={'obsolete_file_key': None},
    )
    deps.resource_event_repo.get_by_idempotency_key.return_value = prior_event
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = None

    result = await complete_document_upload(deps.uow, 'staging/key')

    assert result.already_completed is True
    assert result.document_id == deps.document.id


@pytest.mark.asyncio
async def test_complete_event_for_other_event_type_is_ignored(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    deps.resource_event_repo.get_by_idempotency_key.return_value = (
        SimpleNamespace(event_type='upload_failed', resource_id=4, data={})
    )
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = None

    result = await complete_document_upload(deps.uow, 'staging/key')

    assert result.ignored is True
    assert result.already_completed is False
    assert result.document_id == deps.document.id


@pytest.mark.asyncio
async def test_complete_document_upload_rejects_unexpected_staging_key(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    intent = make_document_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent

    with pytest.raises(InvalidDocumentStateException):
        await complete_document_upload(deps.uow, 'uploads/wrong/key')


@pytest.mark.asyncio
async def test_complete_document_upload_ignores_deleted_document(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    intent = make_document_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.document_repo.get_document.return_value = None

    result = await complete_document_upload(deps.uow, intent.object_key)

    assert result.ignored is True
    deps.upload_intent_repo.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )
    assert deps.uow.commit.await_count == 1


@pytest.mark.asyncio
async def test_complete_upload_rejects_document_not_uploading(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    intent = make_document_upload_intent(deps)
    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent

    with pytest.raises(InvalidDocumentStateException):
        await complete_document_upload(deps.uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_upload_rejects_deleted_row_during_update(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    intent = make_document_upload_intent(deps)

    deps.resource_event_repo.get_by_idempotency_key.return_value = None
    deps.upload_intent_repo.get_by_object_key_for_update.return_value = intent
    deps.document_repo.get_document.return_value = replace(
        deps.document, file=None, status=DocumentStatus.UPLOADING
    )
    deps.document_repo.update_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await complete_document_upload(deps.uow, intent.object_key)


@pytest.mark.asyncio
async def test_get_document_events_authorizes_and_forwards_pagination(
    document_upload_dependencies,
):
    deps = document_upload_dependencies
    pagination = PaginationDTO(limit=5)
    expected = CursorPage([], pagination)
    deps.resource_event_repo.get_events.return_value = expected

    result = await get_document_events(
        deps.uow, 2, 7, deps.document.id, pagination
    )

    assert result is expected
    deps.resource_event_repo.get_events.assert_awaited_once_with(
        2, 'document', deps.document.id, pagination
    )


@pytest.mark.asyncio
async def test_update_document_records_changed_description(repos, storage):
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
        UpdateDocumentDTO(description='Updated description'),
    )

    event_call = unit_of_work.resource_event_repository.create_event.await_args
    assert event_call.args[4] == 'metadata_changed'
    assert event_call.args[5] == {
        'changes': {'description': {'old': None, 'new': 'Updated description'}}
    }
