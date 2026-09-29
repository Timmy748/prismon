from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from project.dtos.asset import (
    ApproveAssetDTO,
    AssetDTO,
    CreateAssetDTO,
    UpdateAssetDTO,
)
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.asset import AssetStatus
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    AssetNotFoundException,
    InsufficientProjectPermissionException,
    InvalidAssetStateException,
    ProjectNotFoundException,
)
from project.use_cases.assets import (
    add_asset,
    delete_asset,
    get_assets,
    review_asset,
    update_asset,
)


@pytest.fixture
def asset_dependencies():
    now = datetime.now(timezone.utc)
    project = Mock()
    project.id = 8
    project_repo = Mock()
    project_repo.get_project = AsyncMock(return_value=project)
    member_repo = Mock()
    member_repo.get_members = AsyncMock(
        return_value=CursorPage(
            [
                MemberDTO(
                    1, 8, MemberRole.OWNER, MemberStatus.ACTIVE, 12, now, now
                )
            ],
            PaginationDTO(),
        )
    )
    asset = AssetDTO(
        3,
        8,
        'projects/8/assets/original',
        'logo',
        None,
        AssetStatus.PENDING,
        now,
        now,
    )
    asset_repo = Mock()
    asset_repo.get_assets = AsyncMock(
        return_value=CursorPage([], PaginationDTO())
    )
    asset_repo.get_asset = AsyncMock(return_value=asset)
    asset_repo.create_asset = AsyncMock(return_value=asset)
    asset_repo.update_asset = AsyncMock(return_value=asset)
    asset_repo.delete_asset = AsyncMock()
    storage = Mock()
    return project_repo, member_repo, asset_repo, storage, asset


@pytest.mark.asyncio
async def test_get_assets_checks_read_permission_and_forwards_filters(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    page = await get_assets(
        project_repo,
        member_repo,
        asset_repo,
        storage,
        8,
        12,
        PaginationDTO(limit=5),
        'logo',
        AssetStatus.ACTIVE,
    )
    assert page == asset_repo.get_assets.return_value
    asset_repo.get_assets.assert_awaited_once_with(
        8, PaginationDTO(limit=5), 'logo', AssetStatus.ACTIVE
    )
    member_repo.get_members.assert_awaited_once()


@pytest.mark.asyncio
async def test_asset_access_rejects_missing_project(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    project_repo.get_project.return_value = None
    with pytest.raises(ProjectNotFoundException):
        await get_assets(project_repo, member_repo, asset_repo, storage, 8, 12)
    member_repo.get_members.assert_not_awaited()


@pytest.mark.asyncio
async def test_asset_access_rejects_non_member(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    member_repo.get_members.return_value = CursorPage([], PaginationDTO())
    with pytest.raises(ProjectNotFoundException):
        await get_assets(project_repo, member_repo, asset_repo, storage, 8, 12)


@pytest.mark.asyncio
async def test_asset_access_rejects_missing_permission(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    member_repo.get_members.return_value.items[0] = MemberDTO(
        1,
        8,
        MemberRole.COLLABORATOR,
        MemberStatus.ACTIVE,
        12,
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
    )
    with pytest.raises(InsufficientProjectPermissionException):
        await add_asset(
            project_repo,
            member_repo,
            asset_repo,
            storage,
            8,
            12,
            CreateAssetDTO('', '', 'logo', '', ''),
            b'bytes',
        )
    storage.save.assert_not_called()


@pytest.mark.asyncio
async def test_add_asset_owner_is_active_and_stores_content(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    result = await add_asset(
        project_repo,
        member_repo,
        asset_repo,
        storage,
        8,
        12,
        CreateAssetDTO('', '', 'logo', 'ignored name', 'description'),
        b'bytes',
    )
    assert result == asset
    key = storage.save.call_args.args[0]
    assert key.startswith('projects/8/assets/')
    storage.save.assert_called_once_with(key, b'bytes')
    asset_repo.create_asset.assert_awaited_once_with(
        project_id=8,
        file=key,
        asset_type='logo',
        description='description',
        status=AssetStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_add_asset_regular_member_is_pending_and_empty_description_none(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    member_repo.get_members.return_value.items[0] = MemberDTO(
        1,
        8,
        MemberRole.MEMBER,
        MemberStatus.ACTIVE,
        12,
        datetime.now(timezone.utc),
        datetime.now(timezone.utc),
    )
    await add_asset(
        project_repo,
        member_repo,
        asset_repo,
        storage,
        8,
        12,
        CreateAssetDTO('', '', 'photo', '', ''),
        b'x',
    )
    assert (
        asset_repo.create_asset.call_args.kwargs['status']
        is AssetStatus.PENDING
    )
    assert asset_repo.create_asset.call_args.kwargs['description'] is None


@pytest.mark.asyncio
async def test_add_asset_cleans_storage_if_repository_fails(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    asset_repo.create_asset.side_effect = RuntimeError
    with pytest.raises(RuntimeError):
        await add_asset(
            project_repo,
            member_repo,
            asset_repo,
            storage,
            8,
            12,
            CreateAssetDTO('', '', 'photo', '', ''),
            b'x',
        )
    storage.delete.assert_called_once_with(storage.save.call_args.args[0])


@pytest.mark.asyncio
async def test_update_asset_replaces_storage_and_updates_metadata(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    result = await update_asset(
        project_repo,
        member_repo,
        asset_repo,
        storage,
        8,
        12,
        3,
        UpdateAssetDTO(type='icon', description='new'),
        b'new bytes',
    )
    assert result == asset
    key = storage.save.call_args.args[0]
    assert key.startswith('projects/8/assets/')
    asset_repo.update_asset.assert_awaited_once_with(
        3, file=key, asset_type='icon', description='new'
    )
    storage.delete.assert_called_once_with(asset.file)


@pytest.mark.asyncio
async def test_update_asset_without_content_leaves_storage_unchanged(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    await update_asset(
        project_repo,
        member_repo,
        asset_repo,
        storage,
        8,
        12,
        3,
        UpdateAssetDTO(type='icon'),
    )
    storage.save.assert_not_called()
    storage.delete.assert_not_called()
    asset_repo.update_asset.assert_awaited_once_with(
        3, file=None, asset_type='icon', description=None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'missing_or_wrong_project', ['missing', 'wrong_project']
)
async def test_update_asset_rejects_missing_or_foreign_asset(
    asset_dependencies, missing_or_wrong_project
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    asset_repo.get_asset.return_value = (
        None
        if missing_or_wrong_project == 'missing'
        else AssetDTO(
            3,
            99,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )
    with pytest.raises(AssetNotFoundException):
        await update_asset(
            project_repo,
            member_repo,
            asset_repo,
            storage,
            8,
            12,
            3,
            UpdateAssetDTO(),
        )


@pytest.mark.asyncio
async def test_update_asset_cleans_new_file_when_repository_returns_none(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, storage, _ = asset_dependencies
    asset_repo.update_asset.return_value = None
    with pytest.raises(AssetNotFoundException):
        await update_asset(
            project_repo,
            member_repo,
            asset_repo,
            storage,
            8,
            12,
            3,
            UpdateAssetDTO(),
            b'new',
        )
    storage.delete.assert_called_once_with(storage.save.call_args.args[0])


@pytest.mark.asyncio
async def test_delete_asset_deletes_record_and_file(asset_dependencies):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    await delete_asset(project_repo, member_repo, asset_repo, storage, 8, 12, 3)
    asset_repo.delete_asset.assert_awaited_once_with(3)
    storage.delete.assert_called_once_with(asset.file)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'missing_or_wrong_project', ['missing', 'wrong_project']
)
async def test_delete_asset_rejects_missing_or_foreign_asset(
    asset_dependencies, missing_or_wrong_project
):
    project_repo, member_repo, asset_repo, storage, asset = asset_dependencies
    asset_repo.get_asset.return_value = (
        None
        if missing_or_wrong_project == 'missing'
        else AssetDTO(
            3,
            99,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )
    with pytest.raises(AssetNotFoundException):
        await delete_asset(
            project_repo, member_repo, asset_repo, storage, 8, 12, 3
        )
    asset_repo.delete_asset.assert_not_awaited()
    storage.delete.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('accept', 'expected'),
    [
        (True, AssetStatus.ACTIVE),
        (False, AssetStatus.ARCHIVED),
    ],
)
async def test_review_asset_changes_pending_status(
    asset_dependencies, accept, expected
):
    project_repo, member_repo, asset_repo, _, _ = asset_dependencies
    await review_asset(
        project_repo, member_repo, asset_repo, 8, 12, 3, ApproveAssetDTO(accept)
    )
    asset_repo.update_asset.assert_awaited_once_with(3, status=expected)


@pytest.mark.asyncio
async def test_review_asset_rejects_non_pending_state(asset_dependencies):
    project_repo, member_repo, asset_repo, _, asset = asset_dependencies
    asset_repo.get_asset.return_value = AssetDTO(
        asset.id,
        asset.project_id,
        asset.file,
        asset.type,
        asset.description,
        AssetStatus.ACTIVE,
        asset.created_at,
        asset.updated_at,
    )
    with pytest.raises(InvalidAssetStateException):
        await review_asset(
            project_repo,
            member_repo,
            asset_repo,
            8,
            12,
            3,
            ApproveAssetDTO(True),
        )
    asset_repo.update_asset.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'missing_or_wrong_project', ['missing', 'wrong_project']
)
async def test_review_asset_rejects_missing_or_foreign_asset(
    asset_dependencies, missing_or_wrong_project
):
    project_repo, member_repo, asset_repo, _, asset = asset_dependencies
    asset_repo.get_asset.return_value = (
        None
        if missing_or_wrong_project == 'missing'
        else AssetDTO(
            3,
            99,
            asset.file,
            asset.type,
            asset.description,
            asset.status,
            asset.created_at,
            asset.updated_at,
        )
    )
    with pytest.raises(AssetNotFoundException):
        await review_asset(
            project_repo,
            member_repo,
            asset_repo,
            8,
            12,
            3,
            ApproveAssetDTO(True),
        )
    asset_repo.update_asset.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_asset_raises_not_found_if_update_disappears(
    asset_dependencies,
):
    project_repo, member_repo, asset_repo, _, _ = asset_dependencies
    asset_repo.update_asset.return_value = None
    with pytest.raises(AssetNotFoundException):
        await review_asset(
            project_repo,
            member_repo,
            asset_repo,
            8,
            12,
            3,
            ApproveAssetDTO(True),
        )
