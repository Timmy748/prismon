from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from project.dtos.asset import AssetDTO
from project.dtos.document import DocumentDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.dtos.tag import TagDTO
from project.dtos.user import UserDTO
from project.entities.asset import AssetStatus
from project.entities.document import DocumentStatus
from project.entities.member import MemberRole, MemberStatus
from project.repositories.asset import IAssetRepository
from project.repositories.document import IDocumentRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.repositories.tag import ITagRepository
from project.routes.tags import create_tags_router
from project.tests.fixtures.mock import make_unit_of_work


@pytest.fixture
def tag_api():
    project_repo = AsyncMock(spec=IProjectRepository)
    member_repo = AsyncMock(spec=IMemberRepository)
    asset_repo = AsyncMock(spec=IAssetRepository)
    document_repo = AsyncMock(spec=IDocumentRepository)
    tag_repo = AsyncMock(spec=ITagRepository)
    user_client = AsyncMock()

    now = datetime.now(timezone.utc)
    project = ProjectDTO(2, 'Project', 7, now, now)
    user = UserDTO(7, 'ana', 'ana@example.com')
    member = MemberDTO(1, 2, MemberRole.OWNER, MemberStatus.ACTIVE, 7, now, now)
    asset = AssetDTO(
        4,
        2,
        1,
        'projects/2/assets/file',
        'image',
        'cover',
        AssetStatus.ACTIVE,
        now,
        now,
    )
    document = DocumentDTO(
        5,
        2,
        1,
        'projects/2/documents/file',
        'Brief',
        None,
        DocumentStatus.PUBLISHED,
        now,
        now,
    )
    tag = TagDTO(9, 2, 'Brand', 'Branding content', '#AABBCC')

    project_repo.get_project.return_value = project
    member_repo.get_members.return_value = CursorPage(
        [member], PaginationDTO(limit=100)
    )
    asset_repo.get_asset.return_value = asset
    document_repo.get_document.return_value = document
    tag_repo.get_tag.return_value = tag
    tag_repo.get_tags.return_value = [tag]
    tag_repo.create_tag.return_value = tag
    tag_repo.update_tag.return_value = tag
    tag_repo.get_asset_tags.return_value = [tag]
    tag_repo.get_document_tags.return_value = [tag]
    user_client.get_current_user.return_value = user

    unit_of_work = make_unit_of_work(
        project_repo,
        member_repo,
        document_repo=document_repo,
        asset_repo=asset_repo,
        tag_repo=tag_repo,
    )
    app = FastAPI()
    app.include_router(
        create_tags_router(lambda: unit_of_work, lambda: user_client)
    )
    return (
        app,
        project_repo,
        member_repo,
        asset_repo,
        document_repo,
        tag_repo,
        user_client,
        unit_of_work,
        tag,
    )


@pytest_asyncio.fixture
async def tag_client(tag_api):
    async with AsyncClient(
        transport=ASGITransport(app=tag_api[0]), base_url='http://test'
    ) as client:
        yield client
