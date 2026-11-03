from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

import project.public_api as public_api_module
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import ProjectNotFoundException
from project.permissions.actions import ProjectAction
from project.permissions.dtos import ProjectPermissionDTO


@pytest.mark.asyncio
async def test_public_api_get_documents_rejects_unknown_project(
    mock_project_repo, public_api
):
    mock_project_repo.get_project.return_value = None
    with pytest.raises(ProjectNotFoundException):
        await public_api.get_documents(
            99,
            20,
        )


@pytest.mark.asyncio
async def test_public_api_document_url_uses_authorized_document_use_case(
    monkeypatch, public_api
):
    use_case = AsyncMock(return_value='https://rustfs.test/signed')
    monkeypatch.setattr(public_api_module, 'get_document_file_url', use_case)
    uow = public_api.unit_of_work_factory()
    storage = public_api.storage_factory()

    result = await public_api.get_document_file_url(7, 9, 17)

    assert result == 'https://rustfs.test/signed'
    use_case.assert_awaited_once_with(
        uow=uow,
        storage=storage,
        project_id=7,
        user_id=9,
        document_id=17,
    )


@pytest.mark.asyncio
async def test_public_api_asset_url_uses_authorized_asset_use_case(
    monkeypatch, public_api
):
    use_case = AsyncMock(return_value='https://rustfs.test/asset-signed')
    monkeypatch.setattr(public_api_module, 'get_asset_file_url', use_case)
    uow = public_api.unit_of_work_factory()
    storage = public_api.storage_factory()

    result = await public_api.get_asset_file_url(7, 9, 42)

    assert result == 'https://rustfs.test/asset-signed'
    use_case.assert_awaited_once_with(
        uow=uow,
        storage=storage,
        project_id=7,
        user_id=9,
        asset_id=42,
    )


@pytest.mark.asyncio
async def test_public_api_get_documents_rejects_nonmember(
    mock_member_repo, public_api
):
    mock_member_repo.get_members.side_effect = None
    mock_member_repo.get_members.return_value = CursorPage([], PaginationDTO())
    with pytest.raises(ProjectNotFoundException):
        await public_api.get_documents(1, 21)


@pytest.mark.asyncio
async def test_public_api_get_documents_allows_collaborator_read(
    mock_member_repo, mock_document_repo, public_api
):
    now = datetime.now(timezone.utc)
    guest = MemberDTO(
        3, 1, MemberRole.COLLABORATOR, MemberStatus.ACTIVE, 30, now, now
    )
    mock_member_repo.get_members.return_value = CursorPage(
        [guest], PaginationDTO()
    )
    await public_api.get_documents(1, 30)
    mock_document_repo.get_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_api_get_assets__allows_collaborator_read(
    mock_member_repo, mock_asset_repo, public_api
):
    now = datetime.now(timezone.utc)
    guest = MemberDTO(
        3, 1, MemberRole.COLLABORATOR, MemberStatus.ACTIVE, 30, now, now
    )
    mock_member_repo.get_members.return_value = CursorPage(
        [guest], PaginationDTO()
    )
    await public_api.get_assets(
        8,
        12,
    )
    mock_asset_repo.get_assets.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_api_asset_access_rejects_missing_project(
    mock_project_repo, public_api
):
    mock_project_repo.get_project.return_value = None
    with pytest.raises(ProjectNotFoundException):
        await public_api.get_assets(8, 12)


@pytest.mark.asyncio
async def test_public_api_asset_access_rejects_non_member(
    mock_member_repo, public_api
):
    mock_member_repo.get_members.return_value = CursorPage([], PaginationDTO())
    with pytest.raises(ProjectNotFoundException):
        await public_api.get_assets(8, 12)


@pytest.mark.asyncio
async def test_public_api_get_api_key_wraps_use_case(
    key_encryptor, monkeypatch, public_api
):
    use_case = AsyncMock(return_value='decrypted-secret')
    monkeypatch.setattr(public_api_module, 'get_api_key', use_case)
    public_api.encryption_factory = lambda: key_encryptor
    uow = public_api.unit_of_work_factory()

    result = await public_api.get_api_key(12, 34, 56)

    assert result == 'decrypted-secret'
    use_case.assert_awaited_once_with(
        uow=uow,
        project_id=12,
        user_id=34,
        api_key_id=56,
        encryptor=key_encryptor,
    )
    uow.__aenter__.assert_awaited_once()
    uow.__aexit__.assert_awaited_once()


def test_public_api_dispatches_resource_permission(public_api):
    now = datetime.now(timezone.utc)
    owner = MemberDTO(
        10, 20, MemberRole.OWNER, MemberStatus.ACTIVE, 1, now, now
    )

    assert (
        public_api.verify_resource_permission(
            owner, ProjectPermissionDTO(20), ProjectAction.UPDATE
        )
        is True
    )


@pytest.mark.asyncio
async def test_public_api_reads_embedding_sources_from_repositories(
    mock_document_repo, mock_asset_repo, public_api
):
    mock_document_repo.get_document.return_value = None
    mock_asset_repo.get_asset.return_value = None

    assert await public_api.get_document_embedding_source(12) is None
    assert await public_api.get_asset_embedding_source(13) is None

    mock_document_repo.get_document.assert_awaited_once_with(12)
    mock_asset_repo.get_asset.assert_awaited_once_with(13)
