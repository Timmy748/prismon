import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from identity.routes.auth import create_auth_router
from identity.routes.user import create_user_router


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
def user_router_app(
    app: FastAPI,
    mock_user_repo,
    mock_password_hasher,
    mock_token_provider,
) -> FastAPI:
    async def user_repository_factory():
        return mock_user_repo

    router = create_user_router(
        password_hasher_factory=lambda: mock_password_hasher,
        token_provider_factory=lambda: mock_token_provider,
        repository_factory=user_repository_factory,
    )
    app.include_router(router)
    return app


@pytest.fixture
def auth_router_app(
    app: FastAPI,
    mock_user_repo,
    mock_token_repo,
    mock_password_hasher,
    mock_token_provider,
) -> FastAPI:
    async def user_repository_factory():
        return mock_user_repo

    async def token_repository_factory():
        return mock_token_repo

    router = create_auth_router(
        password_hasher_factory=lambda: mock_password_hasher,
        token_provider_factory=lambda: mock_token_provider,
        user_repository_factory=user_repository_factory,
        token_repository_factory=token_repository_factory,
    )
    app.include_router(router)
    return app


@pytest_asyncio.fixture
async def auth_client(auth_router_app: FastAPI) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=auth_router_app), base_url='http://test'
    ) as client:
        yield client


@pytest_asyncio.fixture
async def user_client(user_router_app: FastAPI) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=user_router_app), base_url='http://test'
    ) as client:
        yield client
