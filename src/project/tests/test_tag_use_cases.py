from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from project.dtos.asset import AssetDTO
from project.dtos.document import DocumentDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.dtos.tag import CreateTagDTO, TagDTO, UpdateTagDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus
from project.exceptions import (
    AssetNotFoundException,
    DocumentNotFoundException,
    InsufficientProjectPermissionException,
    ProjectNotFoundException,
    TagNotFoundException,
)
from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.repositories.tag import ITagRepository
from project.tests.fixtures.mock import make_unit_of_work
from project.use_cases.tags import (
    add_tag,
    attach_asset_tag,
    attach_document_tag,
    delete_tag,
    detach_asset_tag,
    detach_document_tag,
    get_asset_tags,
    get_document_tags,
    get_tags,
    update_tag,
)

NOW = datetime.now(timezone.utc)
TAG = TagDTO(9, 2, 'Brand', 'Branding content', '#AABBCC')


def _uow(role=MemberRole.OWNER):
    project_repo = AsyncMock(spec=IProjectRepository)
    member_repo = AsyncMock(spec=IMemberRepository)
    asset_repo = AsyncMock(spec=IAssetRepository)
    document_repo = AsyncMock(spec=IDocumentRepository)
    tag_repo = AsyncMock(spec=ITagRepository)
    project_repo.get_project.return_value = ProjectDTO(
        2, 'Project', 7, NOW, NOW
    )
    member_repo.get_members.return_value = CursorPage(
        [MemberDTO(1, 2, role, MemberStatus.ACTIVE, 7, NOW, NOW)],
        PaginationDTO(limit=100),
    )
    asset_repo.get_asset.return_value = AssetDTO(
        4, 2, 'asset', 'image', None, AssetStatus.ACTIVE, NOW, NOW
    )
    document_repo.get_document.return_value = DocumentDTO(
        5, 2, 'document', 'Brief', None, DocumentStatus.DRAFT, NOW, NOW
    )
    tag_repo.get_tag.return_value = TAG
    unit_of_work = make_unit_of_work(
        project_repo,
        member_repo,
        document_repo=document_repo,
        asset_repo=asset_repo,
        tag_repo=tag_repo,
    )
    return (
        unit_of_work,
        project_repo,
        member_repo,
        asset_repo,
        document_repo,
        tag_repo,
    )


@pytest.mark.asyncio
async def test_get_tags_returns_project_tags_to_active_member():
    uow, _, _, _, _, tag_repo = _uow(MemberRole.COLLABORATOR)
    tag_repo.get_tags.return_value = [TAG]

    result = await get_tags(uow, 2, 7)

    assert result == [TAG]
    tag_repo.get_tags.assert_awaited_once_with(2)


@pytest.mark.asyncio
@pytest.mark.parametrize('role', [MemberRole.OWNER, MemberRole.DIRECTOR])
async def test_add_tag_allows_high_rank_members(role):
    uow, _, _, _, _, tag_repo = _uow(role)
    tag_repo.create_tag.return_value = TAG

    result = await add_tag(uow, 2, 7, CreateTagDTO('Brand', 'Text', '#AABBCC'))

    assert result == TAG
    tag_repo.create_tag.assert_awaited_once_with(2, 'Brand', 'Text', '#AABBCC')
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('role', [MemberRole.MEMBER, MemberRole.COLLABORATOR])
async def test_add_tag_rejects_lower_rank_members(role):
    uow, _, _, _, _, tag_repo = _uow(role)

    with pytest.raises(InsufficientProjectPermissionException):
        await add_tag(uow, 2, 7, CreateTagDTO('Brand', 'Text', '#AABBCC'))

    tag_repo.create_tag.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_tags_rejects_unknown_project():
    uow, project_repo, _, _, _, tag_repo = _uow()
    project_repo.get_project.return_value = None

    with pytest.raises(ProjectNotFoundException):
        await get_tags(uow, 404, 7)

    tag_repo.get_tags.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_tags_rejects_user_without_active_membership():
    uow, _, member_repo, _, _, tag_repo = _uow()
    member_repo.get_members.return_value = CursorPage([], PaginationDTO())

    with pytest.raises(ProjectNotFoundException):
        await get_tags(uow, 2, 99)

    tag_repo.get_tags.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tag_updates_tag_from_same_project():
    uow, _, _, _, _, tag_repo = _uow()
    tag_repo.update_tag.return_value = TAG

    result = await update_tag(uow, 2, 7, 9, UpdateTagDTO(label='Brand'))

    assert result == TAG
    tag_repo.update_tag.assert_awaited_once_with(
        9, label='Brand', description=None, color=None
    )
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_tag_rejects_tag_from_another_project():
    uow, _, _, _, _, tag_repo = _uow()
    tag_repo.get_tag.return_value = TagDTO(9, 3, 'Foreign', 'Text', '#AABBCC')

    with pytest.raises(TagNotFoundException):
        await update_tag(uow, 2, 7, 9, UpdateTagDTO(label='Changed'))

    tag_repo.update_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tag_rejects_missing_row_after_repository_update():
    uow, _, _, _, _, tag_repo = _uow()
    tag_repo.update_tag.return_value = None

    with pytest.raises(TagNotFoundException):
        await update_tag(uow, 2, 7, 9, UpdateTagDTO())


@pytest.mark.asyncio
async def test_delete_tag_removes_tag_from_same_project():
    uow, _, _, _, _, tag_repo = _uow()

    await delete_tag(uow, 2, 7, 9)

    tag_repo.delete_tag.assert_awaited_once_with(9)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_tag_rejects_missing_tag():
    uow, _, _, _, _, tag_repo = _uow()
    tag_repo.get_tag.return_value = None

    with pytest.raises(TagNotFoundException):
        await delete_tag(uow, 2, 7, 404)

    tag_repo.delete_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_asset_tags_returns_linked_tags_for_project_asset():
    uow, _, _, _, _, tag_repo = _uow()
    tag_repo.get_asset_tags.return_value = [TAG]

    result = await get_asset_tags(uow, 2, 7, 4)

    assert result == [TAG]
    tag_repo.get_asset_tags.assert_awaited_once_with(4)


@pytest.mark.asyncio
async def test_get_asset_tags_hides_asset_from_another_project():
    uow, _, _, asset_repo, _, tag_repo = _uow()
    asset_repo.get_asset.return_value = AssetDTO(
        4, 3, 'asset', 'image', None, AssetStatus.ACTIVE, NOW, NOW
    )

    with pytest.raises(AssetNotFoundException):
        await get_asset_tags(uow, 2, 7, 4)

    tag_repo.get_asset_tags.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_asset_tag_rejects_tag_from_another_project():
    uow, _, _, _, _, tag_repo = _uow()
    tag_repo.get_tag.return_value = TagDTO(9, 3, 'Foreign', 'Text', '#AABBCC')

    with pytest.raises(TagNotFoundException):
        await attach_asset_tag(uow, 2, 7, 4, 9)

    tag_repo.attach_asset_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_asset_tag_commits_valid_link():
    uow, _, _, _, _, tag_repo = _uow()

    await attach_asset_tag(uow, 2, 7, 4, 9)

    tag_repo.attach_asset_tag.assert_awaited_once_with(4, 9)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_detach_asset_tag_commits_valid_unlink():
    uow, _, _, _, _, tag_repo = _uow()

    await detach_asset_tag(uow, 2, 7, 4, 9)

    tag_repo.detach_asset_tag.assert_awaited_once_with(4, 9)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_tags_returns_linked_tags_for_project_document():
    uow, _, _, _, _, tag_repo = _uow(MemberRole.MEMBER)
    tag_repo.get_document_tags.return_value = [TAG]

    result = await get_document_tags(uow, 2, 7, 5)

    assert result == [TAG]
    tag_repo.get_document_tags.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_get_document_tags_hides_document_from_another_project():
    uow, _, _, _, document_repo, tag_repo = _uow()
    document_repo.get_document.return_value = DocumentDTO(
        5, 3, 'document', 'Brief', None, DocumentStatus.DRAFT, NOW, NOW
    )

    with pytest.raises(DocumentNotFoundException):
        await get_document_tags(uow, 2, 7, 5)

    tag_repo.get_document_tags.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_document_tag_commits_valid_link():
    uow, _, _, _, _, tag_repo = _uow()

    await attach_document_tag(uow, 2, 7, 5, 9)

    tag_repo.attach_document_tag.assert_awaited_once_with(5, 9)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_detach_document_tag_commits_valid_unlink():
    uow, _, _, _, _, tag_repo = _uow()

    await detach_document_tag(uow, 2, 7, 5, 9)

    tag_repo.detach_document_tag.assert_awaited_once_with(5, 9)
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_attach_document_tag_rejects_missing_document():
    uow, _, _, _, document_repo, tag_repo = _uow()
    document_repo.get_document.return_value = None

    with pytest.raises(DocumentNotFoundException):
        await attach_document_tag(uow, 2, 7, 404, 9)

    tag_repo.attach_document_tag.assert_not_awaited()
