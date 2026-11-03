from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest
from sqlalchemy.dialects import postgresql

from agents.dtos.search import HybridSearchCandidate
from agents.entities.asset_embedding import AssetEmbedding
from agents.entities.document_embedding import DocumentEmbedding
from agents.repositories.asset_embedding import AssetEmbeddingRepository
from agents.repositories.document_embedding import DocumentEmbeddingRepository
from agents.use_cases.search import (
    hybrid_search_assets,
    hybrid_search_documents,
)

RESOURCE_ID = 17
PROJECT_ID = 4
RESULT_LIMIT = 3
ASSET_ID = 28
EMBEDDING_DIMENSION = 256
BM25_RANK = 1
DENSE_RANK = 2


@pytest.mark.parametrize(
    ('repository_class', 'resource_key'),
    [
        (DocumentEmbeddingRepository, 'document_id'),
        (AssetEmbeddingRepository, 'asset_id'),
    ],
)
@pytest.mark.asyncio
async def test_embedding_repository_upserts_text_and_vector(
    repository_class, resource_key
):
    session = AsyncMock()
    repository = repository_class(session)
    vector = np.asarray([0.25, 0.75], dtype=np.float32)

    await repository.upsert_embedding(
        RESOURCE_ID, PROJECT_ID, 'published', 'title: Guide', vector
    )

    session.execute.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert f'ON CONFLICT ({resource_key}) DO UPDATE SET' in compiled
    assert 'content = ' in compiled
    assert 'project_id' in compiled
    assert 'status' in compiled
    assert 'embedding' in compiled
    assert (
        session.execute.await_args.args[0]
        .compile(dialect=postgresql.dialect())
        .params[resource_key]
        == RESOURCE_ID
    )
    parameters = statement.compile(dialect=postgresql.dialect()).params
    assert parameters['project_id'] == PROJECT_ID
    assert parameters['status'] == 'published'
    assert parameters['content'] == 'title: Guide'


@pytest.mark.parametrize(
    ('model', 'resource_key'),
    [
        (DocumentEmbedding, 'document_id'),
        (AssetEmbedding, 'asset_id'),
    ],
)
def test_embedding_models_define_text_and_halfvector_columns(
    model, resource_key
):
    table = model.__table__

    assert resource_key in table.primary_key.columns.keys()
    assert table.c.content.type.python_type is str
    assert table.c.project_id.type.python_type is int
    assert table.c.status.type.python_type is str
    assert table.c.project_id.nullable is True
    assert table.c.status.nullable is True
    assert table.c.embedding.type.__class__.__name__ == 'HALFVEC'
    assert table.c.embedding.type.dim == EMBEDDING_DIMENSION
    vector_index = next(
        index for index in table.indexes if index.name.endswith('_hnsw')
    )
    assert vector_index.dialect_options['postgresql']['using'] == 'hnsw'
    assert vector_index.dialect_options['postgresql']['ops'] == {
        'embedding': 'halfvec_ip_ops'
    }


@pytest.mark.parametrize(
    ('repository_class', 'resource_key', 'resource_type', 'status'),
    [
        (DocumentEmbeddingRepository, 'document_id', 'document', 'published'),
        (AssetEmbeddingRepository, 'asset_id', 'asset', 'active'),
    ],
)
@pytest.mark.asyncio
async def test_repository_hybrid_search_fuses_branches_in_one_query(
    repository_class, resource_key, resource_type, status
):
    result = Mock()
    result.mappings.return_value.all.return_value = [
        {
            'resource_id': RESOURCE_ID,
            'rrf_score': 0.0325,
            'bm25_rank': BM25_RANK,
            'dense_rank': DENSE_RANK,
        }
    ]
    session = AsyncMock()
    session.execute.return_value = result
    repository = repository_class(session)
    vector = np.asarray([0.25, 0.75], dtype=np.float32)

    candidates = await repository.hybrid_search(
        PROJECT_ID, 'installation guide', vector, limit=5, rrf_k=60
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.resource_type == resource_type
    assert candidate.resource_id == RESOURCE_ID
    assert candidate.rank == 1
    assert candidate.rrf_score == pytest.approx(0.0325)
    assert candidate.bm25_rank == BM25_RANK
    assert candidate.dense_rank == DENSE_RANK
    session.execute.assert_awaited_once()

    statement = str(session.execute.await_args.args[0])
    parameters = session.execute.await_args.args[1]
    assert 'AS resource_id' in statement
    assert f'ORDER BY pdb.score({resource_key}) DESC' in statement
    assert 'AS bm25_rank' in statement
    assert 'AS dense_rank' in statement
    assert 'content ||| :query' in statement
    assert 'project_id = :project_id' in statement
    assert 'status = :status' in statement
    assert '1.0 / (:rrf_k + bm25_rank)' in statement
    assert '1.0 / (:rrf_k + dense_rank)' in statement
    assert 'ORDER BY rrf_score DESC, resource_id ASC' in statement
    assert parameters == {
        'query': 'installation guide',
        'query_embedding': '[0.25, 0.75]',
        'project_id': PROJECT_ID,
        'status': status,
        'limit': 5,
        'rrf_k': 60,
    }


@pytest.mark.parametrize(
    'repository_class',
    [
        DocumentEmbeddingRepository,
        AssetEmbeddingRepository,
    ],
)
@pytest.mark.asyncio
async def test_repository_hybrid_search_skips_empty_query(repository_class):
    session = AsyncMock()
    repository = repository_class(session)
    vector = np.asarray([0.25, 0.75], dtype=np.float32)

    result = await repository.hybrid_search(PROJECT_ID, '  ', vector, limit=5)

    assert result == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_document_search_delegates_to_single_hybrid_repository_query():
    uow = Mock()
    expected = [
        HybridSearchCandidate(
            'document', 20, 1, 0.0325, bm25_rank=2, dense_rank=1
        )
    ]
    uow.document_embedding_repository.hybrid_search = AsyncMock(
        return_value=expected
    )
    vector = np.asarray([0.25, 0.75], dtype=np.float32)

    candidates = await hybrid_search_documents(
        uow, PROJECT_ID, 'installation guide', vector, limit=RESULT_LIMIT
    )

    assert candidates == expected
    uow.document_embedding_repository.hybrid_search.assert_awaited_once_with(
        project_id=PROJECT_ID,
        query='installation guide',
        query_embedding=vector,
        limit=RESULT_LIMIT,
        rrf_k=60,
    )


@pytest.mark.asyncio
async def test_hybrid_asset_search_returns_asset_candidates():
    uow = Mock()
    expected = [HybridSearchCandidate('asset', ASSET_ID, 1, 1 / 61, 1, 1)]
    uow.asset_embedding_repository.hybrid_search = AsyncMock(
        return_value=expected
    )
    vector = np.asarray([0.4, 0.6], dtype=np.float32)

    candidates = await hybrid_search_assets(uow, PROJECT_ID, 'red box', vector)

    assert candidates == expected
    uow.asset_embedding_repository.hybrid_search.assert_awaited_once()


@pytest.mark.parametrize(
    ('repository_class', 'table_name'),
    [
        (DocumentEmbeddingRepository, 'document_embeddings'),
        (AssetEmbeddingRepository, 'asset_embeddings'),
    ],
)
@pytest.mark.asyncio
async def test_embedding_repository_deletes_resource_embedding(
    repository_class, table_name
):
    session = AsyncMock()
    repository = repository_class(session)

    await repository.delete_embedding(RESOURCE_ID)

    session.execute.assert_awaited_once()
    statement = str(session.execute.await_args.args[0])
    assert f'DELETE FROM {table_name}' in statement
