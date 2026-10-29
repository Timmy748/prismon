from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

import project.public_api as public_api_module
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import ProjectNotFoundException
from project.permissions import ProjectPermission


@pytest.mark.parametrize(
    ('role', 'permissions'),
    [
        (MemberRole.OWNER, set(ProjectPermission)),
        (MemberRole.DIRECTOR, set(ProjectPermission)),
        (
            MemberRole.MEMBER,
            {
                ProjectPermission.CHAT_READ,
                ProjectPermission.CHAT_CREATE,
                ProjectPermission.CHAT_DELETE,
                ProjectPermission.CHAT_UPDATE,
                ProjectPermission.CHAT_SEND_MESSAGE,
                ProjectPermission.DOCUMENT_CREATE,
                ProjectPermission.DOCUMENT_READ,
                ProjectPermission.DOCUMENT_DELETE,
                ProjectPermission.ASSET_CREATE,
                ProjectPermission.ASSET_READ,
            },
        ),
        (
            MemberRole.COLLABORATOR,
            {
                ProjectPermission.WORKFLOW_USE,
                ProjectPermission.CHAT_READ,
                ProjectPermission.DOCUMENT_READ,
                ProjectPermission.ASSET_READ,
            },
        ),
    ],
)
def test_public_api_has_permission_returns_role_permission_membership(
    role: MemberRole, permissions: set[ProjectPermission], public_api
) -> None:
    for permission in ProjectPermission:
        assert public_api.has_permission(role, permission) == (
            permission in permissions
        )


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
