from datetime import datetime

from infra.tasks import TaskQueue, send_task
from project.dtos.asset import AssetUploadCompletionDTO
from project.dtos.document import DocumentUploadCompletionDTO
from project.dtos.upload_intent import UploadIntentDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.exceptions import (
    AssetNotFoundException,
    DocumentNotFoundException,
    InvalidAssetStateException,
    InvalidDocumentStateException,
)
from project.storage import IStorage
from project.unit_of_work import IProjectUnitOfWork
from project.use_cases.resource_events import record_resource_event


def _enqueue_embedding_refresh(resource_type: str, resource_id: int) -> None:
    send_task(
        f'agents.embeddings.{resource_type}',
        args=[resource_id],
        queue=TaskQueue.LONG,
    )


# ruff: noqa: PLR0913
async def create_upload_intent(
    uow: IProjectUnitOfWork,
    project_id: int,
    *,
    asset_id: int | None = None,
    document_id: int | None = None,
    object_key: str,
    final_file_key: str,
    started_by_member_id: int,
    target_status: str,
    file_extension: str | None,
    content_type: str,
    expires_at: datetime,
    previous_file_key: str | None = None,
) -> UploadIntentDTO:
    return await uow.upload_intent_repository.create_upload_intent(
        project_id,
        asset_id=asset_id,
        document_id=document_id,
        object_key=object_key,
        final_file_key=final_file_key,
        started_by_member_id=started_by_member_id,
        target_status=target_status,
        file_extension=file_extension,
        content_type=content_type,
        expires_at=expires_at,
        previous_file_key=previous_file_key,
    )


async def finalize_upload(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    object_key: str,
) -> AssetUploadCompletionDTO | DocumentUploadCompletionDTO | None:
    intent = await uow.upload_intent_repository.get_by_object_key_for_update(
        object_key
    )
    if intent is None:
        event = await uow.resource_event_repository.get_by_idempotency_key(
            object_key
        )
        cleanup = _cleanup_for_completed_event(event, object_key)
        if cleanup is None:
            return None
        await _delete_objects(storage, cleanup)
        return None

    if not await storage.object_exists(object_key):
        raise FileNotFoundError(
            f'RustFS staging object is not available: {object_key}'
        )
    await storage.copy_object(object_key, intent.final_file_key)

    if intent.asset_id is not None:
        completion = await _complete_asset_upload(uow, intent, object_key)
    elif intent.document_id is not None:
        completion = await _complete_document_upload(uow, intent, object_key)
    else:
        return None

    await uow.commit()
    if not completion.already_completed and not completion.ignored:
        if intent.asset_id is not None:
            _enqueue_embedding_refresh('asset', intent.asset_id)
        elif intent.document_id is not None:
            _enqueue_embedding_refresh('document', intent.document_id)
    await _delete_objects(storage, (object_key, completion.obsolete_file_key))
    return completion


async def complete_asset_upload(
    uow: IProjectUnitOfWork, object_key: str
) -> AssetUploadCompletionDTO:
    intent = await uow.upload_intent_repository.get_by_object_key_for_update(
        object_key
    )
    if intent is None or intent.asset_id is None:
        event = await uow.resource_event_repository.get_by_idempotency_key(
            object_key
        )
        if event is not None:
            return AssetUploadCompletionDTO(
                event.resource_id,
                event.data.get('obsolete_file_key')
                if event.event_type == 'file_changed'
                else None,
                already_completed=True,
            )
        return AssetUploadCompletionDTO(None, None, False, ignored=True)
    completion = await _complete_asset_upload(uow, intent, object_key)
    await uow.commit()
    if not completion.already_completed and not completion.ignored:
        if completion.asset_id is not None:
            _enqueue_embedding_refresh('asset', completion.asset_id)
    return completion


async def complete_document_upload(
    uow: IProjectUnitOfWork, object_key: str
) -> DocumentUploadCompletionDTO:
    intent = await uow.upload_intent_repository.get_by_object_key_for_update(
        object_key
    )
    if intent is None or intent.document_id is None:
        event = await uow.resource_event_repository.get_by_idempotency_key(
            object_key
        )
        if event is not None:
            return DocumentUploadCompletionDTO(
                event.resource_id,
                event.data.get('obsolete_file_key')
                if event.event_type == 'file_changed'
                else None,
                already_completed=event.event_type == 'file_changed',
                ignored=event.event_type != 'file_changed',
            )
        return DocumentUploadCompletionDTO(None, None, False, ignored=True)
    completion = await _complete_document_upload(uow, intent, object_key)
    await uow.commit()
    if not completion.already_completed and not completion.ignored:
        if completion.document_id is not None:
            _enqueue_embedding_refresh('document', completion.document_id)
    return completion


async def _complete_asset_upload(
    uow: IProjectUnitOfWork, intent: UploadIntentDTO, object_key: str
) -> AssetUploadCompletionDTO:
    existing = await uow.resource_event_repository.get_by_idempotency_key(
        object_key
    )
    if existing is not None:
        return AssetUploadCompletionDTO(
            asset_id=existing.resource_id,
            obsolete_file_key=existing.data.get('obsolete_file_key'),
            already_completed=True,
        )
    if intent.asset_id is None:
        return AssetUploadCompletionDTO(None, None, False, ignored=True)

    asset = await uow.asset_repository.get_asset(intent.asset_id)
    if asset is None or asset.project_id != intent.project_id:
        raise AssetNotFoundException(intent.asset_id)
    if asset.status is not AssetStatus.UPLOADING:
        raise InvalidAssetStateException(asset.id, asset.status)
    _validate_object_keys(intent, 'assets', asset.status, True)

    updated = await uow.asset_repository.update_asset(
        asset.id,
        file=intent.final_file_key,
        status=AssetStatus(intent.target_status),
        file_extension=intent.file_extension,
        content_type=intent.content_type,
    )
    if updated is None:
        raise AssetNotFoundException(asset.id)
    await record_resource_event(
        uow,
        intent.project_id,
        'asset',
        asset.id,
        intent.started_by_member_id,
        'file_changed',
        {
            'staging_file_key': object_key,
            'final_file_key': intent.final_file_key,
            'obsolete_file_key': intent.previous_file_key,
            'status': updated.status.value,
            'file_extension': intent.file_extension,
            'content_type': intent.content_type,
        },
        idempotency_key=object_key,
    )
    await uow.upload_intent_repository.delete_upload_intent(intent.id)
    return AssetUploadCompletionDTO(
        asset_id=asset.id,
        obsolete_file_key=intent.previous_file_key,
        already_completed=False,
    )


async def _complete_document_upload(
    uow: IProjectUnitOfWork, intent: UploadIntentDTO, object_key: str
) -> DocumentUploadCompletionDTO:
    existing = await uow.resource_event_repository.get_by_idempotency_key(
        object_key
    )
    if existing is not None:
        return DocumentUploadCompletionDTO(
            document_id=existing.resource_id,
            obsolete_file_key=existing.data.get('obsolete_file_key'),
            already_completed=True,
        )
    if intent.document_id is None:
        return DocumentUploadCompletionDTO(None, None, False, ignored=True)

    document = await uow.document_repository.get_document(intent.document_id)
    if document is None:
        await uow.upload_intent_repository.delete_upload_intent(intent.id)
        return DocumentUploadCompletionDTO(None, None, False, ignored=True)
    _validate_object_keys(intent, 'documents', document.status, False)
    if document.status is not DocumentStatus.UPLOADING:
        raise InvalidDocumentStateException(document.id, document.status)

    updated = await uow.document_repository.update_document(
        document.id,
        file=intent.final_file_key,
        status=DocumentStatus(intent.target_status),
        file_extension=intent.file_extension,
        content_type=intent.content_type,
    )
    if updated is None:
        raise DocumentNotFoundException(document.id)
    await record_resource_event(
        uow,
        intent.project_id,
        'document',
        document.id,
        intent.started_by_member_id,
        'file_changed',
        {
            'staging_file_key': object_key,
            'final_file_key': intent.final_file_key,
            'obsolete_file_key': intent.previous_file_key,
            'status': updated.status.value,
            'file_extension': intent.file_extension,
            'content_type': intent.content_type,
        },
        idempotency_key=object_key,
    )
    await uow.upload_intent_repository.delete_upload_intent(intent.id)
    return DocumentUploadCompletionDTO(
        document_id=document.id,
        obsolete_file_key=intent.previous_file_key,
        already_completed=False,
    )


async def expire_stale_upload_intents(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    cutoff: datetime,
) -> list[str]:
    candidates = await uow.upload_intent_repository.get_expired_upload_intents(
        cutoff
    )
    ready_to_promote: list[str] = []
    for candidate in candidates:
        intent = (
            await uow.upload_intent_repository.get_by_object_key_for_update(
                candidate.object_key
            )
        )
        if intent is None or intent.expires_at > cutoff:
            continue
        if await storage.object_exists(intent.object_key):
            ready_to_promote.append(intent.object_key)
            continue
        await _fail_expired_upload(uow, intent)
        try:
            await storage.delete(intent.object_key)
        except Exception:
            # A later RustFS notification can retry cleanup.
            pass
    return ready_to_promote


async def _fail_expired_upload(
    uow: IProjectUnitOfWork,
    intent: UploadIntentDTO,
) -> None:
    event = await uow.resource_event_repository.get_by_idempotency_key(
        intent.object_key
    )
    if event is not None:
        await uow.upload_intent_repository.delete_upload_intent(intent.id)
        await uow.commit()
        return

    resource_type, resource_id = _resource_for_intent(intent)
    if resource_id is None:
        await uow.upload_intent_repository.delete_upload_intent(intent.id)
        await uow.commit()
        return

    if resource_type == 'asset':
        resource = await uow.asset_repository.get_asset(resource_id)
        if resource is None:
            changed = False
        else:
            status = (
                AssetStatus(intent.target_status)
                if intent.previous_file_key is not None
                else AssetStatus.FAILED
            )
            updated = await uow.asset_repository.update_asset(
                resource_id, status=status
            )
            if updated is None:
                raise AssetNotFoundException(resource_id)
            changed = True
    else:
        resource = await uow.document_repository.get_document(resource_id)
        if resource is not None and resource.status is DocumentStatus.UPLOADING:
            status = (
                DocumentStatus(intent.target_status)
                if intent.previous_file_key is not None
                else DocumentStatus.FAILED
            )
            updated = await uow.document_repository.update_document(
                resource_id, status=status
            )
            if updated is None:
                raise DocumentNotFoundException(resource_id)
            changed = True
        else:
            changed = False

    await record_resource_event(
        uow,
        intent.project_id,
        resource_type,
        resource_id,
        intent.started_by_member_id,
        'upload_failed',
        {
            'object_key': intent.object_key,
            'staging_file_key': intent.object_key,
            'final_file_key': intent.final_file_key,
            'reason': 'expired',
        },
        idempotency_key=intent.object_key,
    )
    await uow.upload_intent_repository.delete_upload_intent(intent.id)
    await uow.commit()
    if changed:
        _enqueue_embedding_refresh(resource_type, resource_id)


def _resource_for_intent(
    intent: UploadIntentDTO,
) -> tuple[str, int | None]:
    if intent.asset_id is not None:
        return 'asset', intent.asset_id
    return 'document', intent.document_id


def _validate_object_keys(
    intent: UploadIntentDTO,
    resource_folder: str,
    status: AssetStatus | DocumentStatus,
    is_asset: bool,
) -> None:
    expected_staging = (
        f'uploads/projects/{intent.project_id}/{resource_folder}/'
    )
    expected_final = f'projects/{intent.project_id}/{resource_folder}/'
    if not intent.object_key.startswith(expected_staging) or not (
        intent.final_file_key.startswith(expected_final)
    ):
        if is_asset:
            assert intent.asset_id is not None
            raise InvalidAssetStateException(intent.asset_id, status)
        assert intent.document_id is not None
        raise InvalidDocumentStateException(intent.document_id, status)


def _cleanup_for_completed_event(
    event, object_key: str
) -> tuple[str, str | None] | None:
    if event is None:
        return None
    if event.event_type == 'file_changed':
        return (
            event.data.get('staging_file_key') or object_key,
            event.data.get('obsolete_file_key'),
        )
    if event.event_type == 'upload_failed':
        return (
            event.data.get('staging_file_key')
            or event.data.get('object_key')
            or object_key,
            None,
        )
    return None


async def _delete_objects(
    storage: IStorage, keys: tuple[str, str | None]
) -> None:
    staging_key, obsolete_file_key = keys
    await storage.delete(staging_key)
    if obsolete_file_key is not None:
        await storage.delete(obsolete_file_key)
