# ruff: noqa: PLR2004

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from infra.app import app
from infra.settings import Settings
from project.routes import rustfs_webhook


@pytest.mark.asyncio
async def test_healthz_returns_success():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get('/healthz')

    assert response.status_code == 200
    assert response.content == b''


@pytest.mark.asyncio
async def test_root_head_returns_success_without_body():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.head('/')

    assert response.status_code == 200
    assert response.content == b''


@pytest.mark.asyncio
async def test_main_app_registers_rustfs_webhook_route(monkeypatch):
    monkeypatch.setattr(
        rustfs_webhook,
        'get_settings',
        lambda: Settings.model_construct(
            RUSTFS_WEBHOOK_AUTH_TOKEN=SecretStr('test-webhook-token'),
            RUSTFS_BUCKET='test-bucket',
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Bearer test-webhook-token'},
            json={'Records': []},
        )

    assert response.status_code == 204


def test_health_route_has_get_and_head_methods():
    health_route = next(
        route
        for route in app.routes
        if getattr(route, 'path', None) == '/healthz'
    )
    root_route = next(
        route for route in app.routes if getattr(route, 'path', None) == '/'
    )

    assert health_route.methods == {'GET'}
    assert root_route.methods == {'HEAD'}
