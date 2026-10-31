from unittest.mock import AsyncMock, Mock

import pytest

import project.storage as storage_module
from infra.settings import Settings
from project.storage import create_storage


class AsyncClientContext:
    def __init__(self, client):
        self.client_instance = client

    async def __aenter__(self):
        return self.client_instance

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class FakeSession:
    def __init__(self, client):
        self.client_instance = client
        self.client_calls = []

    def client(self, *args, **kwargs):
        self.client_calls.append((args, kwargs))
        return AsyncClientContext(self.client_instance)


@pytest.fixture
def rustfs_s3_client():
    client = Mock()
    client.head_bucket = AsyncMock()
    client.create_bucket = AsyncMock()
    client.put_object = AsyncMock()
    client.head_object = AsyncMock()
    client.delete_object = AsyncMock()
    client.generate_presigned_url = AsyncMock(
        return_value='https://rustfs.test/signed'
    )
    return client


@pytest.fixture
def rustfs_test_settings():
    return Settings.model_construct(
        DATABASE_URL='postgresql+psycopg://test:test@localhost/test',
        RUSTFS_ENDPOINT_URL='http://rustfs:9000',
        RUSTFS_PUBLIC_ENDPOINT_URL='http://localhost:9000',
        RUSTFS_BUCKET='test-bucket',
        RUSTFS_ACCESS_KEY='access',
        RUSTFS_SECRET_KEY='secret',
        RUSTFS_REGION='us-east-1',
        RUSTFS_PRESIGNED_URL_TTL_SECONDS=900,
    )


@pytest.fixture
def rustfs_storage(monkeypatch, rustfs_s3_client, rustfs_test_settings):
    session = FakeSession(rustfs_s3_client)
    monkeypatch.setattr(
        storage_module, 'get_settings', lambda: rustfs_test_settings
    )
    monkeypatch.setattr(storage_module.aioboto3, 'Session', lambda: session)
    adapter = create_storage()
    return adapter, rustfs_s3_client, session


@pytest.fixture
def set_required_project_environment(monkeypatch):
    def set_environment(ttl_seconds):
        environment = {
            'DATABASE_URL': 'postgresql+psycopg://test:test@localhost/test',
            'RUSTFS_ENDPOINT_URL': 'http://rustfs:9000',
            'RUSTFS_PUBLIC_ENDPOINT_URL': 'http://localhost:9000',
            'RUSTFS_BUCKET': 'test-bucket',
            'RUSTFS_ACCESS_KEY': 'access',
            'RUSTFS_SECRET_KEY': 'secret',
            'RUSTFS_REGION': 'us-east-1',
            'RUSTFS_PRESIGNED_URL_TTL_SECONDS': str(ttl_seconds),
            'PASSWORD_PEPPER': 'pepper',
            'JWT_SECRET_KEY': 'secret',
            'OTEL_SERVICE_NAME': 'prismon_test',
            'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317',
            'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT': 'http://localhost:4317',
        }
        for variable, value in environment.items():
            monkeypatch.setenv(variable, value)

    return set_environment
