from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from agents.clients.project import IProjectClient
from agents.dtos.project_resource import EmbeddingSourceDTO
from agents.embedding_engine.base import IEmbeddingEngine
from agents.repositories.asset_embedding import IAssetEmbeddingRepository
from agents.repositories.document_embedding import IDocumentEmbeddingRepository
from agents.unit_of_work import IAgentsUnitOfWork
from agents.use_cases.embeddings import embed_asset, embed_document

EXPECTED_REFRESH_ATTEMPTS = 2


def _setup(resource_type: str):
    project_client = AsyncMock(spec=IProjectClient)
    repository_spec = (
        IDocumentEmbeddingRepository
        if resource_type == 'document'
        else IAssetEmbeddingRepository
    )
    uow = Mock(spec=IAgentsUnitOfWork)
    repository = AsyncMock(spec=repository_spec)
    setattr(uow, f'{resource_type}_embedding_repository', repository)
    uow.commit = AsyncMock()
    engine = AsyncMock(spec=IEmbeddingEngine)
    getattr(engine, f'embedding_{resource_type}').return_value = np.array(
        [0.1], dtype=np.float32
    )
    method = getattr(project_client, f'get_{resource_type}_embedding_source')
    embed = embed_document if resource_type == 'document' else embed_asset
    return project_client, uow, repository, engine, method, embed


@pytest.mark.asyncio
@pytest.mark.parametrize('resource_type', ['document', 'asset'])
async def test_embedding_refresh_stops_if_resource_disappears_before_upsert(
    resource_type,
):
    client, uow, repository, engine, get_source, embed = _setup(resource_type)
    get_source.side_effect = [
        EmbeddingSourceDTO('title', None, 4, 'active'),
        None,
    ]

    assert await embed(client, uow, engine, 12) is False

    repository.upsert_embedding.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_asset_skips_initially_missing_resource():
    client, uow, repository, engine, get_source, embed = _setup('asset')
    get_source.return_value = None

    assert await embed(client, uow, engine, 12) is False

    engine.embedding_asset.assert_not_awaited()
    repository.upsert_embedding.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_asset_removes_embedding_if_asset_is_deleted_after_commit():
    client, uow, repository, engine, get_source, embed = _setup('asset')
    asset = EmbeddingSourceDTO('title', 'text', 4, 'active')
    get_source.side_effect = [asset, asset, None]

    assert await embed(client, uow, engine, 12) is False

    repository.upsert_embedding.assert_awaited_once()
    repository.delete_embedding.assert_awaited_once_with(12)
    assert uow.commit.await_count == EXPECTED_REFRESH_ATTEMPTS


@pytest.mark.asyncio
@pytest.mark.parametrize('resource_type', ['document', 'asset'])
async def test_embedding_refresh_retries_if_project_or_status_changes(
    resource_type,
):
    client, uow, repository, engine, get_source, embed = _setup(resource_type)
    original = EmbeddingSourceDTO('title', 'text', 4, 'active')
    changed = EmbeddingSourceDTO('title', 'text', 5, 'archived')
    get_source.side_effect = [original, changed, changed, changed, changed]

    assert await embed(client, uow, engine, 12) is True

    assert (
        getattr(engine, f'embedding_{resource_type}').await_count
        == EXPECTED_REFRESH_ATTEMPTS
    )
    repository.upsert_embedding.assert_awaited_once_with(
        12,
        5,
        'archived',
        'title: title | text: text',
        np.array([0.1], dtype=np.float32),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('resource_type', ['document', 'asset'])
async def test_embedding_refresh_removes_stale_commit_and_retries(
    resource_type,
):
    client, uow, repository, engine, get_source, embed = _setup(resource_type)
    original = EmbeddingSourceDTO('title', 'text', 4, 'active')
    changed = EmbeddingSourceDTO('new title', 'new text', 4, 'active')
    get_source.side_effect = [
        original,
        original,
        changed,
        changed,
        changed,
        changed,
    ]

    assert await embed(client, uow, engine, 12) is True

    assert repository.upsert_embedding.await_count == EXPECTED_REFRESH_ATTEMPTS
    assert uow.commit.await_count == EXPECTED_REFRESH_ATTEMPTS
    assert (
        getattr(engine, f'embedding_{resource_type}').await_count
        == EXPECTED_REFRESH_ATTEMPTS
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('resource_type', ['document', 'asset'])
async def test_embedding_refresh_fails_after_repeated_metadata_changes(
    resource_type,
):
    client, uow, repository, engine, get_source, embed = _setup(resource_type)
    original = EmbeddingSourceDTO('title', 'text', 4, 'active')
    changed = EmbeddingSourceDTO('changed', 'text', 4, 'active')
    get_source.side_effect = [original, changed] * 3

    with pytest.raises(RuntimeError, match='metadata changed repeatedly'):
        await embed(client, uow, engine, 12)

    repository.upsert_embedding.assert_not_awaited()
