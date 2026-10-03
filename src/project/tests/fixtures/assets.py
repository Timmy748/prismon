from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from project.clients.client_user import IUserClient
from project.dtos.asset import AssetDTO
from project.dtos.member import MemberDTO
from project.dtos.page import CursorPage, PaginationDTO
from project.dtos.project import ProjectDTO
from project.dtos.user import UserDTO
from project.entities.asset import AssetStatus
from project.entities.member import MemberRole, MemberStatus
from project.repositories.asset import IAssetRepository
from project.repositories.member import IMemberRepository
from project.repositories.project import IProjectRepository
from project.routes.assets import create_assets_router
from project.storage import IStorage


@pytest.fixture
def asset_api():
    project_repo = AsyncMock(spec=IProjectRepository)
    member_repo = AsyncMock(spec=IMemberRepository)
    asset_repo = AsyncMock(spec=IAssetRepository)
    user_client = AsyncMock(spec=IUserClient)
    storage = MagicMock(spec=IStorage)
    now = datetime.now(timezone.utc)
    user = UserDTO(7, 'ana', 'ana@example.com')
    project = ProjectDTO(2, 'Project', 7, now, now)
    member = MemberDTO(1, 2, MemberRole.OWNER, MemberStatus.ACTIVE, 7, now, now)
    asset = AssetDTO(
        4,
        2,
        'projects/2/assets/file',
        'image',
        'cover',
        AssetStatus.ACTIVE,
        now,
        now,
    )
    user_client.get_current_user.return_value = user
    project_repo.get_project.return_value = project
    member_repo.get_members.return_value = CursorPage(
        [member], PaginationDTO(limit=100)
    )
    asset_repo.get_assets.return_value = CursorPage(
        [asset], PaginationDTO(limit=10)
    )
    asset_repo.create_asset.return_value = asset
    asset_repo.update_asset.return_value = asset
    asset_repo.get_asset.return_value = asset

    async def project_factory():
        return project_repo

    async def member_factory():
        return member_repo

    async def asset_factory():
        return asset_repo

    app = FastAPI()
    app.include_router(
        create_assets_router(
            project_factory,
            member_factory,
            asset_factory,
            lambda: storage,
            lambda: user_client,
        )
    )
    return (
        app,
        project_repo,
        member_repo,
        asset_repo,
        user_client,
        storage,
        asset,
    )


@pytest_asyncio.fixture
async def asset_client(asset_api):
    async with AsyncClient(
        transport=ASGITransport(app=asset_api[0]), base_url='http://test'
    ) as client:
        yield client
