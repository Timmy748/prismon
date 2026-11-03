from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.dtos.search import HybridSearchCandidate
from agents.entities.asset_embedding import AssetEmbedding
from agents.repositories.hybrid_search import (
    RRF_K,
    HybridSearchRequest,
    HybridSearchTarget,
)
from agents.repositories.hybrid_search import (
    hybrid_search as _run_hybrid_search,
)
from infra.logs import get_logger

logger = get_logger(__name__)
ASSET_SEARCH_TARGET = HybridSearchTarget(
    resource_type='asset',
    table='asset_embeddings',
    id_column='asset_id',
    status='active',
)


class IAssetEmbeddingRepository(Protocol):
    async def upsert_embedding(
        self,
        asset_id: int,
        project_id: int,
        status: str,
        content: str,
        embedding: NDArray[np.float32],
    ) -> None: ...

    async def hybrid_search(
        self,
        project_id: int,
        query: str,
        query_embedding: NDArray[np.float32],
        limit: int = 10,
        rrf_k: int = RRF_K,
    ) -> list[HybridSearchCandidate]: ...

    async def delete_embedding(self, asset_id: int) -> None: ...


class AssetEmbeddingRepository(IAssetEmbeddingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_embedding(
        self,
        asset_id: int,
        project_id: int,
        status: str,
        content: str,
        embedding: NDArray[np.float32],
    ) -> None:
        statement = insert(AssetEmbedding).values(
            asset_id=asset_id,
            project_id=project_id,
            status=status,
            content=content,
            embedding=embedding.tolist(),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AssetEmbedding.asset_id],
            set_={
                'project_id': project_id,
                'status': status,
                'content': content,
                'embedding': embedding.tolist(),
            },
        )
        await self._session.execute(statement)
        logger.info('Upserted asset embedding: asset_id=%d', asset_id)

    async def hybrid_search(
        self,
        project_id: int,
        query: str,
        query_embedding: NDArray[np.float32],
        limit: int = 10,
        rrf_k: int = RRF_K,
    ) -> list[HybridSearchCandidate]:
        request = HybridSearchRequest(
            project_id=project_id,
            query=query,
            query_embedding=query_embedding,
            limit=limit,
            rrf_k=rrf_k,
        )
        return await _run_hybrid_search(
            self._session,
            target=ASSET_SEARCH_TARGET,
            request=request,
        )

    async def delete_embedding(self, asset_id: int) -> None:
        await self._session.execute(
            delete(AssetEmbedding).where(AssetEmbedding.asset_id == asset_id)
        )
