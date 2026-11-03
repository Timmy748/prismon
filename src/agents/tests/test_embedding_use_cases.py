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

EXPECTED_ATTEMPTS_AFTER_METADATA_CHANGE = 2
EXPECTED_COMMITS_AFTER_POST_COMMIT_DELETE = 2


def _agents_uow(resource_type):
    uow = Mock(spec=IAgentsUnitOfWork)
    repository_interface = (
        IDocumentEmbeddingRepository
        if resource_type == 'document'
        else IAssetEmbeddingRepository
    )
    repository = AsyncMock(spec=repository_interface)
    setattr(uow, f'{resource_type}_embedding_repository', repository)
    uow.commit = AsyncMock()
    return uow, repository


@pytest.mark.asyncio
async def test_embed_document_saves_combined_metadata_and_embedding():
    project_client = AsyncMock(spec=IProjectClient)
    project_client.get_document_embedding_source.return_value = (
        EmbeddingSourceDTO('Guide', 'Setup steps', 4, 'published')
    )
    agents_uow, embedding_repo = _agents_uow('document')
    engine = AsyncMock(spec=IEmbeddingEngine)
    vector = np.asarray([0.2, 0.8], dtype=np.float32)
    engine.embedding_document.return_value = vector

    result = await embed_document(project_client, agents_uow, engine, 17)

    assert result is True
    engine.embedding_document.assert_awaited_once_with('Guide', 'Setup steps')
    embedding_repo.upsert_embedding.assert_awaited_once_with(
        17,
        4,
        'published',
        'title: Guide | text: Setup steps',
        vector,
    )
    agents_uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_asset_saves_combined_metadata_and_embedding():
    project_client = AsyncMock(spec=IProjectClient)
    project_client.get_asset_embedding_source.return_value = EmbeddingSourceDTO(
        'Red box', 'Front view', 4, 'active'
    )
    agents_uow, embedding_repo = _agents_uow('asset')
    engine = AsyncMock(spec=IEmbeddingEngine)
    vector = np.asarray([0.4, 0.6], dtype=np.float32)
    engine.embedding_asset.return_value = vector

    result = await embed_asset(project_client, agents_uow, engine, 28)

    assert result is True
    engine.embedding_asset.assert_awaited_once_with('Red box', 'Front view')
    embedding_repo.upsert_embedding.assert_awaited_once_with(
        28,
        4,
        'active',
        'title: Red box | text: Front view',
        vector,
    )
    agents_uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_document_recomputes_when_metadata_changes_mid_request():
    old_document = EmbeddingSourceDTO(
        'Old title', 'Old description', 4, 'published'
    )
    new_document = EmbeddingSourceDTO(
        'New title', 'New description', 4, 'published'
    )
    project_client = AsyncMock(spec=IProjectClient)
    project_client.get_document_embedding_source.side_effect = [
        old_document,
        new_document,
        new_document,
        new_document,
        new_document,
    ]
    agents_uow, embedding_repo = _agents_uow('document')
    engine = AsyncMock(spec=IEmbeddingEngine)
    latest_vector = np.asarray([0.1, 0.9], dtype=np.float32)
    engine.embedding_document.side_effect = [
        np.asarray([0.9, 0.1], dtype=np.float32),
        latest_vector,
    ]

    result = await embed_document(project_client, agents_uow, engine, 17)

    assert result is True
    assert (
        engine.embedding_document.await_count
        == EXPECTED_ATTEMPTS_AFTER_METADATA_CHANGE
    )
    embedding_repo.upsert_embedding.assert_awaited_once_with(
        17,
        4,
        'published',
        'title: New title | text: New description',
        latest_vector,
    )
    agents_uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_document_removes_upsert_after_resource_deletion():
    document = EmbeddingSourceDTO('Guide', 'Setup steps', 4, 'published')
    project_client = AsyncMock(spec=IProjectClient)
    project_client.get_document_embedding_source.side_effect = [
        document,
        document,
        None,
    ]
    agents_uow, embedding_repo = _agents_uow('document')
    engine = AsyncMock(spec=IEmbeddingEngine)
    engine.embedding_document.return_value = np.asarray(
        [0.2, 0.8], dtype=np.float32
    )

    result = await embed_document(project_client, agents_uow, engine, 17)

    assert result is False
    embedding_repo.upsert_embedding.assert_awaited_once()
    embedding_repo.delete_embedding.assert_awaited_once_with(17)
    assert (
        agents_uow.commit.await_count
        == EXPECTED_COMMITS_AFTER_POST_COMMIT_DELETE
    )


@pytest.mark.asyncio
async def test_embed_document_skips_missing_resource_without_persisting():
    project_client = AsyncMock(spec=IProjectClient)
    project_client.get_document_embedding_source.return_value = None
    agents_uow, embedding_repo = _agents_uow('document')
    engine = AsyncMock(spec=IEmbeddingEngine)

    result = await embed_document(project_client, agents_uow, engine, 17)

    assert result is False
    engine.embedding_document.assert_not_awaited()
    embedding_repo.upsert_embedding.assert_not_awaited()
    agents_uow.commit.assert_not_awaited()
