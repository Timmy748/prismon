from unittest.mock import AsyncMock

import numpy as np
import pytest
from sqlalchemy.dialects import postgresql

from agents.entities.asset_embedding import AssetEmbedding
from agents.entities.document_embedding import DocumentEmbedding
from agents.repositories.asset_embedding import AssetEmbeddingRepository
from agents.repositories.document_embedding import DocumentEmbeddingRepository

RESOURCE_ID = 17
EMBEDDING_DIMENSION = 256


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

    await repository.upsert_embedding(RESOURCE_ID, 'title: Guide', vector)

    session.execute.assert_awaited_once()
    statement = session.execute.await_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert f'ON CONFLICT ({resource_key}) DO UPDATE SET' in compiled
    assert 'content = %(param_1)s' in compiled
    assert 'embedding = %(param_2)s' in compiled
    assert (
        session.execute.await_args.args[0]
        .compile(dialect=postgresql.dialect())
        .params[resource_key]
        == RESOURCE_ID
    )


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
    assert table.c.embedding.type.__class__.__name__ == 'HALFVEC'
    assert table.c.embedding.type.dim == EMBEDDING_DIMENSION
    vector_index = next(
        index for index in table.indexes if index.name.endswith('_hnsw')
    )
    assert vector_index.dialect_options['postgresql']['using'] == 'hnsw'
    assert vector_index.dialect_options['postgresql']['ops'] == {
        'embedding': 'halfvec_ip_ops'
    }
