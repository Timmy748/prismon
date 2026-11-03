# ruff: noqa: PLR0912, PLR0913, PLR0917
from datetime import UTC, datetime, timedelta
from secrets import token_hex

from infra.logs import get_logger
from infra.settings import get_settings
from infra.tasks import TaskQueue, send_task
from project.dtos.asset import (
    ApproveAssetDTO,
    AssetDTO,
    AssetUploadCompletionDTO,
    AssetUploadDTO,
    CreateAssetDTO,
    StartAssetUploadDTO,
    UpdateAssetDTO,
)
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.resource_event import ResourceEventDTO
from project.entities.asset import AssetStatus
from project.entities.member import MemberStatus
from project.exceptions import (
    AssetNotFoundException,
    InsufficientProjectPermissionException,
    InvalidAssetStateException,
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
    complete_asset_upload as complete_asset_upload_intent,
)
from project.use_cases.upload_intents import create_upload_intent
from project.utils.files import build_download_filename, file_extension

logger = get_logger(__name__)


async def _get_active_member(
    uow: IProjectUnitOfWork, project_id: int, user_id: int
):
    members = await uow.member_repository.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    if not members.items:
        raise ProjectNotFoundException(project_id)
    return members.items[0]


async def _authorize_asset_access(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    permission: ProjectPermission,
):
    if await uow.project_repository.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    member = await _get_active_member(uow, project_id, user_id)
    if not has_permission(member.role, permission):
        raise InsufficientProjectPermissionException(permission)
    return member


def _asset_upload_status(member) -> AssetStatus:
    return (
        AssetStatus.ACTIVE
        if has_permission(member.role, ProjectPermission.ASSET_APPROVE)
        else AssetStatus.PENDING
    )


async def start_asset_upload(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: StartAssetUploadDTO,
) -> AssetUploadDTO:
    member = await _authorize_asset_access(
        uow, project_id, user_id, ProjectPermission.ASSET_CREATE
    )
    now = datetime.now(UTC)
    ttl = get_settings().RUSTFS_PRESIGNED_URL_TTL_SECONDS
    expires_at = now + timedelta(seconds=ttl)
    upload_id = token_hex(16)
    key = f'uploads/projects/{project_id}/assets/{upload_id}'
    final_file_key = f'projects/{project_id}/assets/{upload_id}'
    upload_url = await storage.generate_presigned_put_url(
        key, data.content_type, ttl
    )
    target_status = _asset_upload_status(member)
    asset = await uow.asset_repository.create_asset(
        project_id=project_id,
        file=None,
        asset_type=data.type,
        created_by_member_id=member.id,
        name=data.name,
        description=data.description or None,
        status=AssetStatus.UPLOADING,
    )
    extension = file_extension(
        data.original_filename or data.name, data.content_type
    )
    await create_upload_intent(
        uow,
        project_id,
        asset_id=asset.id,
        object_key=key,
        final_file_key=final_file_key,
        started_by_member_id=member.id,
        target_status=target_status.value,
        file_extension=extension,
        content_type=data.content_type,
        expires_at=expires_at,
    )
    await record_resource_event(
        uow,
        project_id,
        'asset',
        asset.id,
        member.id,
        'resource_created',
        {
            'name': data.name,
            'type': data.type,
            'description': data.description or None,
        },
    )
    await record_resource_event(
        uow,
        project_id,
        'asset',
        asset.id,
        member.id,
        'upload_started',
        {
            'object_key': key,
            'final_file_key': final_file_key,
            'expires_at': expires_at.isoformat(),
        },
    )
    await uow.commit()
    send_task(
        'agents.embeddings.asset',
        args=[asset.id],
        queue=TaskQueue.LONG,
    )
    return AssetUploadDTO(
        asset=asset,
        upload_url=upload_url,
        expires_at=expires_at,
        required_headers={'Content-Type': data.content_type},
    )


async def start_asset_replacement(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
    content_type: str = 'application/octet-stream',
    original_filename: str | None = None,
) -> AssetUploadDTO:
    member = await _authorize_asset_access(
        uow, project_id, user_id, ProjectPermission.ASSET_UPDATE
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    if asset.status is AssetStatus.UPLOADING:
        raise InvalidAssetStateException(asset_id, asset.status)

    target_status = (
        _asset_upload_status(member)
        if asset.status is AssetStatus.FAILED
        else asset.status
    )
    now = datetime.now(UTC)
    ttl = get_settings().RUSTFS_PRESIGNED_URL_TTL_SECONDS
    expires_at = now + timedelta(seconds=ttl)
    upload_id = token_hex(16)
    key = f'uploads/projects/{project_id}/assets/{upload_id}'
    final_file_key = f'projects/{project_id}/assets/{upload_id}'
    upload_url = await storage.generate_presigned_put_url(
        key, content_type, ttl
    )
    updated = await uow.asset_repository.update_asset(
        asset_id, status=AssetStatus.UPLOADING
    )
    if updated is None:
        raise AssetNotFoundException(asset_id)
    extension = file_extension(original_filename or asset.name, content_type)
    await create_upload_intent(
        uow,
        project_id,
        asset_id=asset_id,
        object_key=key,
        final_file_key=final_file_key,
        started_by_member_id=member.id,
        target_status=target_status.value,
        file_extension=extension,
        content_type=content_type,
        expires_at=expires_at,
        previous_file_key=asset.file,
    )
    await record_resource_event(
        uow,
        project_id,
        'asset',
        asset_id,
        member.id,
        'upload_started',
        {
            'object_key': key,
            'final_file_key': final_file_key,
            'previous_file_key': asset.file,
            'expires_at': expires_at.isoformat(),
        },
    )
    await uow.commit()
    return AssetUploadDTO(
        asset=updated,
        upload_url=upload_url,
        expires_at=expires_at,
        required_headers={'Content-Type': content_type},
    )


async def get_assets(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
    asset_type: str | None = None,
    status: AssetStatus | None = None,
) -> CursorPage[AssetDTO]:
    await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_READ,
    )
    del storage  # Listing returns metadata; file contents remain in storage.
    page = await uow.asset_repository.get_assets(
        project_id, pagination, asset_type, status
    )
    logger.debug(
        'Assets loaded: project_id=%s count=%s', project_id, len(page.items)
    )
    return page


async def _get_asset_for_read(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
) -> AssetDTO:
    await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_READ,
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    return asset


async def get_asset_file_url(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
    *,
    internal: bool = False,
) -> str:
    asset = await _get_asset_for_read(uow, project_id, user_id, asset_id)
    if asset.file is None:
        raise InvalidAssetStateException(asset_id, asset.status)
    download_options = {
        'download_filename': build_download_filename(
            asset.name,
            asset.file_extension,
            fallback=f'asset-{asset.id}',
        ),
        'disposition': 'inline',
    }
    if asset.content_type is not None:
        download_options['content_type'] = asset.content_type
    if internal:
        download_options['endpoint_url'] = get_settings().RUSTFS_ENDPOINT_URL
    return await storage.get_presigned_url(asset.file, **download_options)


async def download_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
) -> str:
    asset = await _get_asset_for_read(uow, project_id, user_id, asset_id)
    if asset.file is None:
        raise InvalidAssetStateException(asset_id, asset.status)
    filename = build_download_filename(
        asset.name,
        asset.file_extension,
        fallback=f'asset-{asset.id}',
    )
    download_options = {'download_filename': filename}
    if asset.content_type is not None:
        download_options['content_type'] = asset.content_type
    return await storage.get_presigned_url(asset.file, **download_options)


async def add_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: CreateAssetDTO,
    content: bytes,
    content_type: str | None = None,
) -> AssetDTO:
    member = await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_CREATE,
    )
    key = f'projects/{project_id}/assets/{token_hex(16)}'
    await storage.save(key, content, content_type)
    status = _asset_upload_status(member)
    try:
        asset = await uow.asset_repository.create_asset(
            project_id=project_id,
            file=key,
            asset_type=data.type,
            created_by_member_id=member.id,
            name=data.name,
            description=data.description or None,
            status=status,
            file_extension=file_extension(data.file or data.name, content_type),
            content_type=content_type,
        )
        await record_resource_event(
            uow,
            project_id,
            'asset',
            asset.id,
            member.id,
            'resource_created',
            {
                'type': data.type,
                'description': data.description or None,
            },
        )
        await uow.commit()
        logger.info('Asset created: project_id=%s', project_id)
    except Exception:
        logger.exception('Asset creation failed: project_id=%s', project_id)
        await storage.delete(key)
        raise
    send_task(
        'agents.embeddings.asset',
        args=[asset.id],
        queue=TaskQueue.LONG,
    )
    return asset


async def update_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
    data: UpdateAssetDTO,
    content: bytes | None = None,
    content_type: str | None = None,
) -> AssetDTO:
    member = await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_UPDATE,
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    if asset.status is AssetStatus.UPLOADING:
        raise InvalidAssetStateException(asset_id, asset.status)
    new_key = asset.file
    if content is not None:
        new_key = f'projects/{project_id}/assets/{token_hex(16)}'
        await storage.save(new_key, content, content_type)
    try:
        metadata_updates = {'name': data.name} if data.name is not None else {}
        file_metadata = (
            {
                'file_extension': file_extension('', content_type)
                or asset.file_extension,
                'content_type': content_type,
            }
            if content is not None
            else {}
        )
        updated = await uow.asset_repository.update_asset(
            asset_id,
            file=new_key if content is not None else None,
            asset_type=data.type,
            description=data.description,
            **metadata_updates,
            **file_metadata,
        )
        if updated is None:
            raise AssetNotFoundException(asset_id)
        changes = {}
        if data.type is not None and data.type != asset.type:
            changes['type'] = {'old': asset.type, 'new': data.type}
        if data.name is not None and data.name != asset.name:
            changes['name'] = {'old': asset.name, 'new': data.name}
        if (
            data.description is not None
            and data.description != asset.description
        ):
            changes['description'] = {
                'old': asset.description,
                'new': data.description,
            }
        if changes:
            await record_resource_event(
                uow,
                project_id,
                'asset',
                asset_id,
                member.id,
                'metadata_changed',
                {'changes': changes},
            )
        if content is not None:
            await record_resource_event(
                uow,
                project_id,
                'asset',
                asset_id,
                member.id,
                'file_changed',
                {
                    'old_file_key': asset.file,
                    'new_file_key': new_key,
                },
            )
        await uow.commit()
        logger.info(
            'Asset updated: project_id=%s asset_id=%s', project_id, asset_id
        )
    except Exception:
        logger.exception(
            'Asset update failed: project_id=%s asset_id=%s',
            project_id,
            asset_id,
        )
        if content is not None:
            await storage.delete(new_key)
        raise
    if content is not None and asset.file is not None:
        await storage.delete(asset.file)
    if 'name' in changes or 'description' in changes:
        send_task(
            'agents.embeddings.asset',
            args=[asset_id],
            queue=TaskQueue.LONG,
        )
    return updated


async def delete_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
) -> None:
    member = await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_UPDATE,
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    if asset.status is AssetStatus.UPLOADING:
        raise InvalidAssetStateException(asset_id, asset.status)
    await record_resource_event(
        uow,
        project_id,
        'asset',
        asset_id,
        member.id,
        'resource_deleted',
        {'file_key': asset.file},
    )
    await uow.asset_repository.delete_asset(asset_id)
    await uow.commit()
    send_task(
        'agents.embeddings.delete_asset',
        args=[asset_id],
        queue=TaskQueue.LONG,
    )
    if asset.file is not None:
        await storage.delete(asset.file)
    logger.info(
        'Asset deleted: project_id=%s asset_id=%s', project_id, asset_id
    )


async def review_asset(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
    data: ApproveAssetDTO,
) -> AssetDTO:
    member = await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_APPROVE,
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    if asset.status is not AssetStatus.PENDING:
        raise InvalidAssetStateException(asset_id, asset.status)
    updated = await uow.asset_repository.update_asset(
        asset_id,
        status=AssetStatus.ACTIVE if data.accept else AssetStatus.ARCHIVED,
    )
    if updated is None:
        raise AssetNotFoundException(asset_id)
    await record_resource_event(
        uow,
        project_id,
        'asset',
        asset_id,
        member.id,
        'status_changed',
        {'old': asset.status.value, 'new': updated.status.value},
    )
    await uow.commit()
    send_task(
        'agents.embeddings.asset',
        args=[asset_id],
        queue=TaskQueue.LONG,
    )
    logger.info(
        'Asset review completed: project_id=%s asset_id=%s accepted=%s',
        project_id,
        asset_id,
        data.accept,
    )
    return updated


async def complete_asset_upload(
    uow: IProjectUnitOfWork, object_key: str
) -> AssetUploadCompletionDTO:
    return await complete_asset_upload_intent(uow, object_key)


async def get_asset_events(
    uow: IProjectUnitOfWork,
    project_id: int,
    user_id: int,
    asset_id: int,
    pagination: PaginationDTO = PaginationDTO(),
) -> CursorPage[ResourceEventDTO]:
    await _authorize_asset_access(
        uow, project_id, user_id, ProjectPermission.ASSET_READ
    )
    return await get_resource_events(
        uow, project_id, 'asset', asset_id, pagination
    )
