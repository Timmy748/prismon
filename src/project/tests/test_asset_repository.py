import pytest

from project.dtos.page import PaginationDTO
from project.entities.asset import AssetStatus
from project.repositories.asset import AssetRepository


@pytest.mark.asyncio
async def test_create_and_get_asset(
    asset_repo: AssetRepository, sample_project
) -> None:
    created = await asset_repo.create_asset(
        sample_project.id, 'https://files.test/logo.svg', 'logo'
    )

    loaded = await asset_repo.get_asset(created.id)

    assert loaded is not None
    assert loaded.file == 'https://files.test/logo.svg'
    assert loaded.type == 'logo'


@pytest.mark.asyncio
async def test_get_assets_filters_type_and_status(
    asset_repo: AssetRepository, sample_project
) -> None:
    wanted = await asset_repo.create_asset(
        sample_project.id, 'url-logo', 'logo', status=AssetStatus.ACTIVE
    )
    await asset_repo.create_asset(
        sample_project.id, 'url-photo', 'photo', status=AssetStatus.ARCHIVED
    )

    page = await asset_repo.get_assets(
        sample_project.id,
        pagination=PaginationDTO(limit=1),
        asset_type='logo',
        status=AssetStatus.ACTIVE,
    )

    assert [item.id for item in page.items] == [wanted.id]
    assert page.pagination.cursor is None
    assert page.pagination.more is False


@pytest.mark.asyncio
async def test_update_and_delete_asset(
    asset_repo: AssetRepository, sample_project
) -> None:
    created = await asset_repo.create_asset(
        sample_project.id, 'url-old', 'logo'
    )

    updated = await asset_repo.update_asset(
        created.id,
        file='url-new',
        asset_type='symbol',
        description='Updated description',
        status=AssetStatus.ARCHIVED,
    )
    deleted = await asset_repo.delete_asset(created.id)

    assert updated is not None and updated.file == 'url-new'
    assert deleted is None
    assert await asset_repo.get_asset(created.id) is None


@pytest.mark.asyncio
async def test_update_asset_returns_none_when_missing(
    asset_repo: AssetRepository,
) -> None:
    result = await asset_repo.update_asset(404, file='missing')

    assert result is None


@pytest.mark.asyncio
async def test_delete_asset_does_nothing_when_missing(
    asset_repo: AssetRepository,
) -> None:
    result = await asset_repo.delete_asset(404)

    assert result is None


@pytest.mark.asyncio
async def test_asset_cursor_returns_older_assets(
    asset_repo: AssetRepository, sample_project
) -> None:
    assets = [
        await asset_repo.create_asset(
            sample_project.id, f'url-{index}', 'graphic'
        )
        for index in range(3)
    ]

    first_page = await asset_repo.get_assets(
        sample_project.id, pagination=PaginationDTO(limit=1)
    )
    second_page = await asset_repo.get_assets(
        sample_project.id,
        pagination=PaginationDTO(limit=1, cursor=first_page.pagination.cursor),
    )

    assert first_page.items[0].id == assets[-1].id
    assert second_page.items[0].id == assets[-2].id
    assert first_page.pagination.more is True
