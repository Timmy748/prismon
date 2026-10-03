from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from project.dtos.member import MemberDTO
from project.dtos.user import UserDTO
from project.entities.member import MemberRole, MemberStatus
from project.routes.members import create_project_members_router


def make_member(
    member_id=11, user_id=19, role=MemberRole.MEMBER, status=MemberStatus.ACTIVE
):
    now = datetime.now(timezone.utc)
    return MemberDTO(
        id=member_id,
        project_id=3,
        role=role,
        status=status,
        user_id=user_id,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def member_route_dependencies():
    user = UserDTO(id=7, username='member', email='member@example.com')
    user_client = AsyncMock()
    user_client.get_current_user.return_value = user
    project_repo, member_repo = AsyncMock(), AsyncMock()
    return project_repo, member_repo, user_client


@pytest.fixture
def member_route_app(member_route_dependencies):
    project_repo, member_repo, user_client = member_route_dependencies

    async def project_factory():
        return project_repo

    async def member_factory():
        return member_repo

    app = FastAPI()
    app.include_router(
        create_project_members_router(
            project_factory, member_factory, lambda: user_client
        )
    )
    return app


@pytest_asyncio.fixture
async def member_route_client(member_route_app):
    async with AsyncClient(
        transport=ASGITransport(app=member_route_app), base_url='http://test'
    ) as client:
        yield client
