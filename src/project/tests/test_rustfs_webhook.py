# ruff: noqa: PLR2004

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from infra.settings import Settings
from project.routes import rustfs_webhook

pytest_plugins = ('project.tests.fixtures.upload_intents',)


@pytest.fixture
def webhook_client(monkeypatch, shared_uow, rustfs_test_settings):
    app = FastAPI()
    app.include_router(
        rustfs_webhook.create_rustfs_webhook_router(lambda: shared_uow)
    )
    monkeypatch.setattr(
        rustfs_webhook, 'get_settings', lambda: rustfs_test_settings
    )
    sender = Mock()
    monkeypatch.setattr(rustfs_webhook, 'send_task', sender)
    should_finalize = AsyncMock(return_value=False)
    monkeypatch.setattr(
        rustfs_webhook, 'should_finalize_upload', should_finalize
    )
    return app, shared_uow, sender, should_finalize


@pytest.mark.asyncio
async def test_webhook_requires_configured_secret(webhook_client, monkeypatch):
    app, _, _, _ = webhook_client
    settings = Settings.model_construct(
        RUSTFS_WEBHOOK_AUTH_TOKEN=SecretStr(''), RUSTFS_BUCKET='test-bucket'
    )
    monkeypatch.setattr(rustfs_webhook, 'get_settings', lambda: settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Bearer x'},
            json={},
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_bearer_token(webhook_client):
    app, _, _, _ = webhook_client

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Basic test-webhook-token'},
            json={'Records': []},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('body', ['{bad json', [], {}])
async def test_webhook_rejects_invalid_event_payload(webhook_client, body):
    app, _, _, _ = webhook_client
    headers = {'Authorization': 'Bearer test-webhook-token'}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        if isinstance(body, str):
            response = await client.post(
                '/internal/webhooks/rustfs', headers=headers, content=body
            )
        else:
            response = await client.post(
                '/internal/webhooks/rustfs', headers=headers, json=body
            )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_webhook_decodes_valid_keys_filters_and_enqueues_long_task(
    webhook_client,
):
    app, uow, sender, should_finalize = webhook_client
    should_finalize.return_value = True
    payload = {
        'Records': [
            {
                'eventName': 's3:ObjectCreated:Put',
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'uploads%2Fmy+file.png'},
                },
            },
            {
                'eventName': 's3:ObjectRemoved:Delete',
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'uploads/ignored'},
                },
            },
            {
                'eventName': 's3:ObjectCreated:Put',
                's3': {
                    'bucket': {'name': 'other'},
                    'object': {'key': 'uploads/wrong-bucket'},
                },
            },
            {
                'eventName': 's3:ObjectCreated:Put',
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'elsewhere/key'},
                },
            },
        ]
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'bEaReR test-webhook-token'},
            json=payload,
        )

    assert response.status_code == 204
    should_finalize.assert_awaited_once_with(uow, 'uploads/my file.png')
    uow.upload_intent_repository.get_by_object_key.assert_not_awaited()
    uow.resource_event_repository.get_by_idempotency_key.assert_not_awaited()
    sender.assert_called_once_with(
        'project.uploads.finalize',
        args=['uploads/my file.png'],
        queue='long_tasks',
    )


@pytest.mark.asyncio
async def test_webhook_enqueues_duplicate_event_for_cleanup(webhook_client):
    app, _, sender, should_finalize = webhook_client
    should_finalize.return_value = True
    payload = {
        'EventName': 's3:ObjectCreated:CompleteMultipartUpload',
        'Records': [
            {
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 'uploads/stage'},
                }
            }
        ],
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Bearer test-webhook-token'},
            json=payload,
        )

    assert response.status_code == 204
    sender.assert_called_once()


@pytest.mark.asyncio
async def test_webhook_ignores_unknown_staging_object(webhook_client):
    app, uow, sender, should_finalize = webhook_client

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Bearer test-webhook-token'},
            json={
                'Records': [
                    {
                        'eventName': 's3:ObjectCreated:Put',
                        's3': {
                            'bucket': {'name': 'test-bucket'},
                            'object': {'key': 'uploads/unknown'},
                        },
                    }
                ]
            },
        )

    assert response.status_code == 204
    should_finalize.assert_awaited_once_with(uow, 'uploads/unknown')
    sender.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_skips_malformed_records_and_non_string_keys(
    webhook_client,
):
    app, uow, sender, should_finalize = webhook_client
    payload = {
        'Records': [
            None,
            {'eventName': 's3:ObjectCreated:Put', 's3': None},
            {
                'eventName': 's3:ObjectCreated:Put',
                's3': {'bucket': None, 'object': {}},
            },
            {
                'eventName': 's3:ObjectCreated:Put',
                's3': {
                    'bucket': {'name': 'test-bucket'},
                    'object': {'key': 10},
                },
            },
        ]
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Bearer test-webhook-token'},
            json=payload,
        )

    assert response.status_code == 204
    should_finalize.assert_not_awaited()
    sender.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_reports_queue_failure_for_retry(webhook_client):
    app, _, sender, should_finalize = webhook_client
    should_finalize.return_value = True
    sender.side_effect = RuntimeError('broker unavailable')

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.post(
            '/internal/webhooks/rustfs',
            headers={'Authorization': 'Bearer test-webhook-token'},
            json={
                'Records': [
                    {
                        'eventName': 's3:ObjectCreated:Put',
                        's3': {
                            'bucket': {'name': 'test-bucket'},
                            'object': {'key': 'uploads/key'},
                        },
                    }
                ]
            },
        )

    assert response.status_code == 503
    assert response.json() == {'detail': 'Could not queue upload finalization'}
