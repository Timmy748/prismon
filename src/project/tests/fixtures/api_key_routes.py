from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from project.routes.api_keys import create_api_keys_router


@pytest.fixture
def api_key_direct_router(api_key_context, key_encryptor):
    uow, _, _, _ = api_key_context

    @asynccontextmanager
    async def context():
        yield uow

    user_client = SimpleNamespace(
        get_current_user=AsyncMock(return_value=SimpleNamespace(id=1))
    )
    return create_api_keys_router(
        context, lambda: user_client, lambda: key_encryptor
    )


@pytest_asyncio.fixture
async def api_key_route_client(api_key_context, key_encryptor):
    uow, _, _, _ = api_key_context

    @asynccontextmanager
    async def unit_of_work_factory():
        yield uow

    user_client = SimpleNamespace(
        get_current_user=AsyncMock(
            side_effect=lambda token: SimpleNamespace(id=int(token))
        )
    )
    app = FastAPI()
    app.include_router(
        create_api_keys_router(
            unit_of_work_factory, lambda: user_client, lambda: key_encryptor
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        yield client
