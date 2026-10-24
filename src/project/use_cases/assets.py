# ruff: noqa: PLR0913, PLR0917
from uuid import uuid4

from core.logs import get_logger
from project.dtos.asset import (
    ApproveAssetDTO,
    AssetDTO,
    CreateAssetDTO,
    UpdateAssetDTO,
)
from project.dtos.page import CursorPage, PaginationDTO
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


async def add_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: CreateAssetDTO,
    content: bytes,
) -> AssetDTO:
    member = await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_CREATE,
    )
    key = f'projects/{project_id}/assets/{uuid4().hex}'
    storage.save(key, content)
    status = (
        AssetStatus.ACTIVE
        if has_permission(member.role, ProjectPermission.ASSET_APPROVE)
        else AssetStatus.PENDING
    )
    try:
        asset = await uow.asset_repository.create_asset(
            project_id=project_id,
            file=key,
            asset_type=data.type,
            description=data.description or None,
            status=status,
        )
        await uow.commit()
        logger.info('Asset created: project_id=%s', project_id)
        return asset
    except Exception:
        logger.exception('Asset creation failed: project_id=%s', project_id)
        storage.delete(key)
        raise


async def update_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
    data: UpdateAssetDTO,
    content: bytes | None = None,
) -> AssetDTO:
    await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_UPDATE,
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    new_key = asset.file
    if content is not None:
        new_key = f'projects/{project_id}/assets/{uuid4().hex}'
        storage.save(new_key, content)
    try:
        updated = await uow.asset_repository.update_asset(
            asset_id,
            file=new_key if content is not None else None,
            asset_type=data.type,
            description=data.description,
        )
        if updated is None:
            raise AssetNotFoundException(asset_id)
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
            storage.delete(new_key)
        raise
    if content is not None:
        storage.delete(asset.file)
    return updated


async def delete_asset(
    uow: IProjectUnitOfWork,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
) -> None:
    await _authorize_asset_access(
        uow,
        project_id,
        user_id,
        ProjectPermission.ASSET_UPDATE,
    )
    asset = await uow.asset_repository.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    await uow.asset_repository.delete_asset(asset_id)
    await uow.commit()
    storage.delete(asset.file)
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
    await _authorize_asset_access(
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
    await uow.commit()
    logger.info(
        'Asset review completed: project_id=%s asset_id=%s accepted=%s',
        project_id,
        asset_id,
        data.accept,
    )
    return updated
