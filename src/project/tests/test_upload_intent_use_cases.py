from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from infra.tasks import TaskQueue
from project.dtos.asset import AssetDTO
from project.dtos.document import DocumentDTO
from project.dtos.upload_intent import UploadIntentDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.exceptions import (
    AssetNotFoundException,
    DocumentNotFoundException,
    InvalidAssetStateException,
    InvalidDocumentStateException,
)
from project.use_cases.upload_intents import (
    _cleanup_for_completed_event,
    _complete_asset_upload,
    _complete_document_upload,
    _delete_objects,
    complete_asset_upload,
    complete_document_upload,
    create_upload_intent,
    expire_stale_upload_intents,
    finalize_upload,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)
ASSET_ID = 7
DOCUMENT_ID = 8


def _intent(**overrides):
    values = {
        'id': 1,
        'project_id': 3,
        'asset_id': 7,
        'document_id': None,
        'object_key': 'uploads/projects/3/assets/incoming',
        'final_file_key': 'projects/3/assets/complete',
        'started_by_member_id': 11,
        'target_status': 'active',
        'file_extension': 'svg',
        'content_type': 'image/svg+xml',
        'expires_at': NOW + timedelta(hours=1),
        'previous_file_key': 'projects/3/assets/old',
        'created_at': NOW,
    }
    values.update(overrides)
    return UploadIntentDTO(**values)


def _asset(**overrides):
    values = {
        'id': 7,
        'project_id': 3,
        'created_by_member_id': 11,
        'file': None,
        'type': 'image',
        'description': None,
        'status': AssetStatus.UPLOADING,
        'created_at': NOW,
        'updated_at': NOW,
    }
    values.update(overrides)
    return AssetDTO(**values)


def _document(**overrides):
    values = {
        'id': 8,
        'project_id': 3,
        'created_by_member_id': 11,
        'file': None,
        'name': 'document',
        'description': None,
        'status': DocumentStatus.UPLOADING,
        'created_at': NOW,
        'updated_at': NOW,
    }
    values.update(overrides)
    return DocumentDTO(**values)


def _uow():
    return SimpleNamespace(
        upload_intent_repository=SimpleNamespace(
            create_upload_intent=AsyncMock(),
            get_by_object_key=AsyncMock(),
            get_by_object_key_for_update=AsyncMock(return_value=None),
            get_expired_upload_intents=AsyncMock(return_value=[]),
            delete_upload_intent=AsyncMock(),
        ),
        resource_event_repository=SimpleNamespace(
            get_by_idempotency_key=AsyncMock(return_value=None),
            create_event=AsyncMock(),
        ),
        asset_repository=SimpleNamespace(
            get_asset=AsyncMock(return_value=_asset()),
            update_asset=AsyncMock(
                return_value=_asset(status=AssetStatus.ACTIVE)
            ),
        ),
        document_repository=SimpleNamespace(
            get_document=AsyncMock(return_value=_document()),
            update_document=AsyncMock(
                return_value=_document(status=DocumentStatus.PUBLISHED)
            ),
        ),
        commit=AsyncMock(),
    )


def _storage(*, exists=True):
    return SimpleNamespace(
        object_exists=AsyncMock(return_value=exists),
        copy_object=AsyncMock(),
        delete=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_create_upload_intent_forwards_all_values():
    uow = _uow()
    expected = object()
    uow.upload_intent_repository.create_upload_intent.return_value = expected

    result = await create_upload_intent(
        uow,
        3,
        asset_id=7,
        object_key='staging',
        final_file_key='final',
        started_by_member_id=11,
        target_status='active',
        file_extension='svg',
        content_type='image/svg+xml',
        expires_at=NOW,
        previous_file_key='old',
    )

    assert result is expected
    uow.upload_intent_repository.create_upload_intent.assert_awaited_once_with(
        3,
        asset_id=7,
        document_id=None,
        object_key='staging',
        final_file_key='final',
        started_by_member_id=11,
        target_status='active',
        file_extension='svg',
        content_type='image/svg+xml',
        expires_at=NOW,
        previous_file_key='old',
    )


@pytest.mark.asyncio
async def test_finalize_without_intent_and_without_event_is_ignored():
    uow = _uow()
    storage = _storage()

    result = await finalize_upload(uow, storage, 'staging')

    assert result is None
    storage.delete.assert_not_awaited()


@pytest.mark.parametrize(
    ('event_type', 'data', 'expected'),
    [
        (
            'file_changed',
            {'staging_file_key': 'stage', 'obsolete_file_key': 'old'},
            ('stage', 'old'),
        ),
        ('upload_failed', {'object_key': 'failed'}, ('failed', None)),
        ('metadata_changed', {}, None),
    ],
)
@pytest.mark.asyncio
async def test_finalize_without_intent_uses_event_to_retry_cleanup(
    event_type, data, expected
):
    uow = _uow()
    uow.resource_event_repository.get_by_idempotency_key.return_value = (
        SimpleNamespace(event_type=event_type, data=data)
    )
    storage = _storage()

    result = await finalize_upload(uow, storage, 'staging')

    assert result is None
    if expected is None:
        storage.delete.assert_not_awaited()
    else:
        assert [call.args[0] for call in storage.delete.await_args_list] == [
            key for key in expected if key is not None
        ]


@pytest.mark.asyncio
async def test_finalize_rejects_staging_object_not_yet_visible():
    uow = _uow()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        _intent()
    )
    storage = _storage(exists=False)

    with pytest.raises(FileNotFoundError, match='not available'):
        await finalize_upload(
            uow, storage, 'uploads/projects/3/assets/incoming'
        )

    storage.copy_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_asset_promotes_file_commits_and_cleans_old_file(
    stub_embedding_enqueue,
):
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    storage = _storage()

    result = await finalize_upload(uow, storage, intent.object_key)

    assert result.asset_id == ASSET_ID
    storage.copy_object.assert_awaited_once_with(
        intent.object_key, intent.final_file_key
    )
    uow.commit.assert_awaited_once()
    stub_embedding_enqueue.assert_called_once_with(
        'agents.embeddings.asset', args=[ASSET_ID], queue=TaskQueue.LONG
    )
    assert [call.args[0] for call in storage.delete.await_args_list] == [
        intent.object_key,
        intent.previous_file_key,
    ]


@pytest.mark.asyncio
async def test_finalize_document_promotes_file_without_old_file_cleanup(
    stub_embedding_enqueue,
):
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/complete',
        target_status='published',
        previous_file_key=None,
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    storage = _storage()

    result = await finalize_upload(uow, storage, intent.object_key)

    assert result.document_id == DOCUMENT_ID
    storage.delete.assert_awaited_once_with(intent.object_key)
    uow.commit.assert_awaited_once()
    stub_embedding_enqueue.assert_called_once_with(
        'agents.embeddings.document',
        args=[DOCUMENT_ID],
        queue=TaskQueue.LONG,
    )


@pytest.mark.asyncio
async def test_finalize_without_resource_reference_does_not_commit_or_cleanup():
    uow = _uow()
    intent = _intent(asset_id=None, document_id=None)
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    storage = _storage()

    result = await finalize_upload(uow, storage, intent.object_key)

    assert result is None
    uow.commit.assert_not_awaited()
    storage.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_asset_returns_existing_event_as_idempotent_result():
    uow = _uow()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        None
    )
    uow.resource_event_repository.get_by_idempotency_key.return_value = (
        SimpleNamespace(
            resource_id=7,
            event_type='file_changed',
            data={'obsolete_file_key': 'old'},
        )
    )

    result = await complete_asset_upload(uow, 'stage')

    assert result.asset_id == ASSET_ID
    assert result.obsolete_file_key == 'old'
    assert result.already_completed is True


@pytest.mark.asyncio
async def test_complete_asset_returns_event_when_intent_still_exists():
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.resource_event_repository.get_by_idempotency_key.return_value = (
        SimpleNamespace(
            resource_id=7,
            data={'obsolete_file_key': 'old'},
        )
    )

    result = await complete_asset_upload(uow, intent.object_key)

    assert result.already_completed is True
    assert result.obsolete_file_key == 'old'


@pytest.mark.asyncio
async def test_complete_asset_helper_ignores_intent_without_asset_id():
    uow = _uow()

    result = await _complete_asset_upload(
        uow, _intent(asset_id=None, document_id=8), 'stage'
    )

    assert result.ignored is True


@pytest.mark.asyncio
async def test_complete_document_ignores_intent_without_document_id():
    uow = _uow()

    result = await _complete_document_upload(
        uow, _intent(asset_id=7, document_id=None), 'stage'
    )

    assert result.ignored is True


@pytest.mark.asyncio
async def test_complete_document_returns_event_when_intent_still_exists():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/final',
        target_status='published',
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.resource_event_repository.get_by_idempotency_key.return_value = (
        SimpleNamespace(
            resource_id=8,
            data={'obsolete_file_key': 'old'},
        )
    )

    result = await complete_document_upload(uow, intent.object_key)

    assert result.already_completed is True
    assert result.obsolete_file_key == 'old'


@pytest.mark.asyncio
async def test_complete_document_without_intent_or_event_is_ignored():
    uow = _uow()

    result = await complete_document_upload(uow, 'unknown')

    assert result.ignored is True


@pytest.mark.asyncio
async def test_complete_asset_ignores_unknown_or_non_asset_upload():
    uow = _uow()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        _intent(asset_id=None, document_id=8)
    )

    result = await complete_asset_upload(uow, 'stage')

    assert result.ignored is True
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_asset_updates_resource_and_records_event():
    uow = _uow()
    intent = _intent(
        previous_file_key=None,
        expires_at=NOW - timedelta(minutes=1),
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )

    result = await complete_asset_upload(uow, intent.object_key)

    assert result.asset_id == ASSET_ID
    assert result.already_completed is False
    uow.asset_repository.update_asset.assert_awaited_once_with(
        7,
        file=intent.final_file_key,
        status=AssetStatus.ACTIVE,
        file_extension=intent.file_extension,
        content_type=intent.content_type,
    )
    uow.resource_event_repository.create_event.assert_awaited_once()
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        1
    )
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_asset_rejects_missing_resource():
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.asset_repository.get_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await complete_asset_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_asset_rejects_resource_in_another_project():
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.asset_repository.get_asset.return_value = _asset(project_id=99)

    with pytest.raises(AssetNotFoundException):
        await complete_asset_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_asset_rejects_invalid_state():
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.asset_repository.get_asset.return_value = _asset(
        status=AssetStatus.FAILED
    )

    with pytest.raises(InvalidAssetStateException):
        await complete_asset_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_asset_rejects_invalid_object_keys():
    uow = _uow()
    intent = _intent(object_key='wrong/staging')
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )

    with pytest.raises(InvalidAssetStateException):
        await complete_asset_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_asset_rejects_missing_update_result():
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.asset_repository.update_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await complete_asset_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_document_returns_existing_event_idempotently():
    uow = _uow()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        None
    )
    uow.resource_event_repository.get_by_idempotency_key.return_value = (
        SimpleNamespace(
            resource_id=8,
            event_type='file_changed',
            data={'obsolete_file_key': 'old'},
        )
    )

    result = await complete_document_upload(uow, 'stage')

    assert result.document_id == DOCUMENT_ID
    assert result.already_completed is True
    assert result.obsolete_file_key == 'old'


@pytest.mark.asyncio
async def test_complete_document_ignores_existing_non_file_event():
    uow = _uow()
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        None
    )
    uow.resource_event_repository.get_by_idempotency_key.return_value = (
        SimpleNamespace(resource_id=8, event_type='upload_failed', data={})
    )

    result = await complete_document_upload(uow, 'stage')

    assert result.ignored is True
    assert result.already_completed is False


@pytest.mark.asyncio
async def test_complete_document_updates_resource_and_records_event():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/final',
        target_status='published',
        previous_file_key=None,
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )

    result = await complete_document_upload(uow, intent.object_key)

    assert result.document_id == DOCUMENT_ID
    uow.document_repository.update_document.assert_awaited_once_with(
        8,
        file=intent.final_file_key,
        status=DocumentStatus.PUBLISHED,
        file_extension=intent.file_extension,
        content_type=intent.content_type,
    )
    uow.resource_event_repository.create_event.assert_awaited_once()
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        1
    )


@pytest.mark.asyncio
async def test_complete_document_ignores_missing_resource_and_deletes_intent():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/final',
        target_status='published',
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.document_repository.get_document.return_value = None

    result = await complete_document_upload(uow, intent.object_key)

    assert result.ignored is True
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        1
    )


@pytest.mark.asyncio
async def test_complete_document_rejects_invalid_object_keys():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='wrong/staging',
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )

    with pytest.raises(InvalidDocumentStateException):
        await complete_document_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_document_rejects_invalid_state():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/final',
        target_status='published',
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.document_repository.get_document.return_value = _document(
        status=DocumentStatus.DRAFT
    )

    with pytest.raises(InvalidDocumentStateException):
        await complete_document_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_complete_document_rejects_missing_update_result():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/final',
        target_status='published',
    )
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.document_repository.update_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await complete_document_upload(uow, intent.object_key)


@pytest.mark.asyncio
async def test_stale_expiration_returns_existing_object_for_finalization():
    uow = _uow()
    storage = _storage()
    expired_intent = _intent(expires_at=NOW - timedelta(minutes=1))
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        expired_intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        expired_intent
    )

    keys = await expire_stale_upload_intents(uow, storage, NOW)

    assert keys == [expired_intent.object_key]


@pytest.mark.asyncio
async def test_expire_stale_upload_intents_skips_deleted_and_extended_rows():
    uow = _uow()
    intent = _intent()
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent,
        intent,
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.side_effect = [
        None,
        _intent(expires_at=NOW + timedelta(days=1)),
    ]
    storage = _storage()

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    storage.object_exists.assert_not_awaited()


@pytest.mark.asyncio
async def test_expiration_fails_missing_upload_and_deletes_staging():
    uow = _uow()
    intent = _intent(
        previous_file_key=None, expires_at=NOW - timedelta(minutes=1)
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    storage = _storage(exists=False)

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    assert uow.asset_repository.update_asset.await_args.kwargs == {
        'status': AssetStatus.FAILED
    }
    uow.resource_event_repository.create_event.assert_awaited_once()
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        1
    )
    storage.delete.assert_awaited_once_with(intent.object_key)


@pytest.mark.asyncio
async def test_expiration_records_event_when_document_is_no_longer_uploading():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=DOCUMENT_ID,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/complete',
        expires_at=NOW - timedelta(minutes=1),
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.document_repository.get_document.return_value = _document(
        status=DocumentStatus.PUBLISHED
    )
    storage = _storage(exists=False)

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    uow.document_repository.update_document.assert_not_awaited()
    uow.resource_event_repository.create_event.assert_awaited_once()
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )


@pytest.mark.asyncio
async def test_expire_stale_upload_intents_ignores_staging_cleanup_error():
    uow = _uow()
    intent = _intent(
        previous_file_key=None,
        expires_at=NOW - timedelta(minutes=1),
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    storage = _storage(exists=False)
    storage.delete.side_effect = OSError('temporary storage failure')

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []


@pytest.mark.asyncio
async def test_expire_stale_asset_when_resource_was_removed_records_failure():
    uow = _uow()
    intent = _intent(
        expires_at=NOW - timedelta(minutes=1),
        previous_file_key=None,
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.asset_repository.get_asset.return_value = None
    storage = _storage(exists=False)

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    uow.resource_event_repository.create_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_expire_stale_asset_rejects_failed_repository_update():
    uow = _uow()
    intent = _intent(
        expires_at=NOW - timedelta(minutes=1),
        previous_file_key=None,
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.asset_repository.update_asset.return_value = None

    with pytest.raises(AssetNotFoundException):
        await expire_stale_upload_intents(uow, _storage(exists=False), NOW)


@pytest.mark.asyncio
async def test_expire_stale_document_rejects_failed_repository_update():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        object_key='uploads/projects/3/documents/incoming',
        final_file_key='projects/3/documents/final',
        target_status='published',
        expires_at=NOW - timedelta(minutes=1),
        previous_file_key=None,
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.document_repository.update_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await expire_stale_upload_intents(uow, _storage(exists=False), NOW)


@pytest.mark.asyncio
async def test_stale_replacement_restores_document_status():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=8,
        expires_at=NOW - timedelta(minutes=1),
        target_status='published',
        previous_file_key='old',
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.document_repository.get_document.return_value = _document(
        status=DocumentStatus.UPLOADING
    )
    storage = _storage(exists=False)

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    uow.document_repository.update_document.assert_awaited_once_with(
        8, status=DocumentStatus.PUBLISHED
    )
    uow.commit.assert_awaited_once()
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )


@pytest.mark.asyncio
async def test_stale_expiration_with_existing_event_only_cleans_intent():
    uow = _uow()
    intent = _intent(expires_at=NOW - timedelta(minutes=1))
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    uow.resource_event_repository.get_by_idempotency_key.return_value = object()
    storage = _storage(exists=False)

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )
    uow.commit.assert_awaited_once()
    uow.resource_event_repository.create_event.assert_not_awaited()
    storage.delete.assert_awaited_once_with(intent.object_key)


@pytest.mark.asyncio
async def test_stale_malformed_intent_without_resource_is_discarded():
    uow = _uow()
    intent = _intent(
        asset_id=None,
        document_id=None,
        previous_file_key=None,
        expires_at=NOW - timedelta(minutes=1),
    )
    uow.upload_intent_repository.get_expired_upload_intents.return_value = [
        intent
    ]
    uow.upload_intent_repository.get_by_object_key_for_update.return_value = (
        intent
    )
    storage = _storage(exists=False)

    result = await expire_stale_upload_intents(uow, storage, NOW)

    assert result == []
    uow.upload_intent_repository.delete_upload_intent.assert_awaited_once_with(
        intent.id
    )
    uow.commit.assert_awaited_once()
    uow.resource_event_repository.create_event.assert_not_awaited()
    storage.delete.assert_awaited_once_with(intent.object_key)


@pytest.mark.parametrize(
    ('event', 'object_key', 'expected'),
    [
        (None, 'stage', None),
        (
            SimpleNamespace(event_type='file_changed', data={}),
            'stage',
            ('stage', None),
        ),
        (
            SimpleNamespace(
                event_type='file_changed',
                data={'staging_file_key': 'stage', 'obsolete_file_key': 'old'},
            ),
            'other',
            ('stage', 'old'),
        ),
        (
            SimpleNamespace(event_type='upload_failed', data={}),
            'stage',
            ('stage', None),
        ),
        (
            SimpleNamespace(event_type='metadata_changed', data={}),
            'stage',
            None,
        ),
    ],
)
def test_cleanup_for_completed_event_maps_supported_events(
    event, object_key, expected
):
    assert _cleanup_for_completed_event(event, object_key) == expected


@pytest.mark.asyncio
async def test_delete_objects_removes_staging_and_previous_file():
    storage = _storage()

    await _delete_objects(storage, ('stage', 'old'))

    assert [call.args[0] for call in storage.delete.await_args_list] == [
        'stage',
        'old',
    ]


@pytest.mark.asyncio
async def test_delete_objects_skips_absent_previous_file():
    storage = _storage()

    await _delete_objects(storage, ('stage', None))

    storage.delete.assert_awaited_once_with('stage')
