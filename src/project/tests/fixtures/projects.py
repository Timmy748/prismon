from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from project.dtos.project import ProjectDTO
from project.dtos.user import UserDTO
from project.routes.projects import create_project_router
from project.tests.fixtures.mock import make_unit_of_work


@pytest.fixture
def project_route_dependencies():
    project_repo = Mock()
    for method in (
        'get_projects_for_member',
        'create_project',
        'get_project',
        'update_project',
        'delete_project',
    ):
        setattr(project_repo, method, AsyncMock())
    member_repo = Mock()
    for method in ('create_member', 'get_members'):
        setattr(member_repo, method, AsyncMock())
    user_client = Mock()
    user_client.get_current_user = AsyncMock()
    user_client.get_by_id = AsyncMock()
    return project_repo, member_repo, user_client


@pytest.fixture
def project_route_app(project_route_dependencies):
    project_repo, member_repo, user_client = project_route_dependencies
    unit_of_work = make_unit_of_work(project_repo, member_repo)

    app = FastAPI()
    app.include_router(
        create_project_router(lambda: unit_of_work, lambda: user_client)
    )
    return app


@pytest_asyncio.fixture
async def project_http_client(project_route_app):
    async with AsyncClient(
        transport=ASGITransport(app=project_route_app), base_url='http://test'
    ) as client:
        yield client


@pytest.fixture
def authenticated_project_user(project_route_dependencies):
    user_client = project_route_dependencies[2]
    user_client.get_current_user.return_value = UserDTO(
        7, 'ana', 'ana@example.com'
    )
    return user_client


@pytest.fixture
def sample_project_dto():
    now = datetime.now(timezone.utc)
    return ProjectDTO(12, 'Brand', 7, now, now)
