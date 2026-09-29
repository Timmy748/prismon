# ruff: noqa: PLR0913, PLR0917
from uuid import uuid4

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
from project.repositories.asset import IAssetRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.storage import IStorage


async def _get_active_member(member_repo, project_id: int, user_id: int):
    members = await member_repo.get_members(
        project_id,
        pagination=PaginationDTO(limit=100),
        user_id=user_id,
        status=MemberStatus.ACTIVE,
    )
    if not members.items:
        raise ProjectNotFoundException(project_id)
    return members.items[0]


async def _authorize_asset_access(
    project_repo,
    member_repo,
    project_id: int,
    user_id: int,
    permission: ProjectPermission,
):
    if await project_repo.get_project(project_id) is None:
        raise ProjectNotFoundException(project_id)
    member = await _get_active_member(member_repo, project_id, user_id)
    if not has_permission(member.role, permission):
        raise InsufficientProjectPermissionException(permission)
    return member


async def get_assets(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    asset_repo: IAssetRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    pagination: PaginationDTO = PaginationDTO(),
    asset_type: str | None = None,
    status: AssetStatus | None = None,
) -> CursorPage[AssetDTO]:
    await _authorize_asset_access(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.ASSET_READ,
    )
    del storage  # Listing returns metadata; file contents remain in storage.
    return await asset_repo.get_assets(
        project_id, pagination, asset_type, status
    )


async def add_asset(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    asset_repo: IAssetRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    data: CreateAssetDTO,
    content: bytes,
) -> AssetDTO:
    member = await _authorize_asset_access(
        project_repo,
        member_repo,
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
        return await asset_repo.create_asset(
            project_id=project_id,
            file=key,
            asset_type=data.type,
            description=data.description or None,
            status=status,
        )
    except Exception:
        storage.delete(key)
        raise


async def update_asset(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    asset_repo: IAssetRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
    data: UpdateAssetDTO,
    content: bytes | None = None,
) -> AssetDTO:
    await _authorize_asset_access(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.ASSET_UPDATE,
    )
    asset = await asset_repo.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    new_key = asset.file
    if content is not None:
        new_key = f'projects/{project_id}/assets/{uuid4().hex}'
        storage.save(new_key, content)
    try:
        updated = await asset_repo.update_asset(
            asset_id,
            file=new_key if content is not None else None,
            asset_type=data.type,
            description=data.description,
        )
        if updated is None:
            raise AssetNotFoundException(asset_id)
    except Exception:
        if content is not None:
            storage.delete(new_key)
        raise
    if content is not None:
        storage.delete(asset.file)
    return updated


async def delete_asset(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    asset_repo: IAssetRepository,
    storage: IStorage,
    project_id: int,
    user_id: int,
    asset_id: int,
) -> None:
    await _authorize_asset_access(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.ASSET_UPDATE,
    )
    asset = await asset_repo.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    await asset_repo.delete_asset(asset_id)
    storage.delete(asset.file)


async def review_asset(
    project_repo: IProjectRepository,
    member_repo: IMemberRepository,
    asset_repo: IAssetRepository,
    project_id: int,
    user_id: int,
    asset_id: int,
    data: ApproveAssetDTO,
) -> AssetDTO:
    await _authorize_asset_access(
        project_repo,
        member_repo,
        project_id,
        user_id,
        ProjectPermission.ASSET_APPROVE,
    )
    asset = await asset_repo.get_asset(asset_id)
    if asset is None or asset.project_id != project_id:
        raise AssetNotFoundException(asset_id)
    if asset.status is not AssetStatus.PENDING:
        raise InvalidAssetStateException(asset_id, asset.status)
    updated = await asset_repo.update_asset(
        asset_id,
        status=AssetStatus.ACTIVE if data.accept else AssetStatus.ARCHIVED,
    )
    if updated is None:
        raise AssetNotFoundException(asset_id)
    return updated
