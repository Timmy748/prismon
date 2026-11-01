# ruff: noqa: PLR2004
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from project.dtos.page import PaginationDTO
from project.dtos.tag import TagDTO
from project.entities.asset import Asset, AssetStatus
from project.repositories.asset import AssetRepository

NOW = datetime.now(timezone.utc)


def _tag():
    return SimpleNamespace(
        id=9,
        project_id=2,
        label='Brand',
        description='Branding',
        color='#AABBCC',
    )


def _asset(asset_id=4, tags=None):
    return SimpleNamespace(
        id=asset_id,
        project_id=2,
        file='asset-key',
        type='image',
        description='cover',
        status=AssetStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
        tags=list(tags or []),
    )


def _session(rows=()):
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = list(rows)
    session.scalars = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_asset_repository_maps_attached_tags_on_get():
    session = _session()
    session.get.return_value = _asset(tags=[_tag()])

    result = await AssetRepository(session).get_asset(4)

    assert result.tags == [TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')]


@pytest.mark.asyncio
async def test_asset_repository_get_returns_none_for_missing_row():
    session = _session()

    result = await AssetRepository(session).get_asset(404)

    assert result is None


@pytest.mark.asyncio
async def test_asset_repository_list_maps_tags_and_cursor():
    session = _session([_asset(4, [_tag()]), _asset(3)])

    result = await AssetRepository(session).get_assets(
        2,
        PaginationDTO(limit=1, cursor=(NOW, 5)),
        asset_type='image',
        status=AssetStatus.ACTIVE,
    )

    assert result.items[0].tags == [
        TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')
    ]
    assert result.pagination.more is True
    assert result.pagination.cursor == (NOW, 4)


@pytest.mark.asyncio
async def test_asset_repository_list_returns_empty_page_without_cursor():
    session = _session()

    result = await AssetRepository(session).get_assets(2)

    assert result.items == []
    assert result.pagination.cursor is None
    assert result.pagination.more is False


@pytest.mark.asyncio
async def test_asset_repository_create_returns_empty_tag_list():
    session = _session()

    def refresh(row):
        row.id = 4
        row.created_at = NOW
        row.updated_at = NOW

    session.refresh.side_effect = refresh

    result = await AssetRepository(session).create_asset(
        2, 'asset-key', 'image', 'cover'
    )

    assert result.id == 4
    assert result.tags == []
    assert isinstance(session.add.call_args.args[0], Asset)


@pytest.mark.asyncio
async def test_asset_repository_update_keeps_and_maps_tags():
    session = _session()
    row = _asset(tags=[_tag()])
    session.get.return_value = row

    result = await AssetRepository(session).update_asset(
        4,
        file='new-key',
        asset_type='photo',
        description='new description',
        status=AssetStatus.ARCHIVED,
    )

    assert result.file == 'new-key'
    assert result.type == 'photo'
    assert result.description == 'new description'
    assert result.status is AssetStatus.ARCHIVED
    assert result.tags == [TagDTO(9, 2, 'Brand', 'Branding', '#AABBCC')]


@pytest.mark.asyncio
async def test_asset_repository_update_returns_none_for_missing_row():
    session = _session()

    result = await AssetRepository(session).update_asset(404)

    assert result is None


@pytest.mark.asyncio
async def test_asset_repository_delete_removes_existing_row():
    session = _session()
    row = _asset()
    session.get.return_value = row

    await AssetRepository(session).delete_asset(4)

    session.delete.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_asset_repository_delete_ignores_missing_row():
    session = _session()

    await AssetRepository(session).delete_asset(404)

    session.delete.assert_not_awaited()
