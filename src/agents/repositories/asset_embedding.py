from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.entities.asset_embedding import AssetEmbedding
from infra.logs import get_logger

logger = get_logger(__name__)


class IAssetEmbeddingRepository(Protocol):
    async def upsert_embedding(
        self,
        asset_id: int,
        content: str,
        embedding: NDArray[np.float32],
    ) -> None: ...


class AssetEmbeddingRepository(IAssetEmbeddingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_embedding(
        self,
        asset_id: int,
        content: str,
        embedding: NDArray[np.float32],
    ) -> None:
        statement = insert(AssetEmbedding).values(
            asset_id=asset_id,
            content=content,
            embedding=embedding.tolist(),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AssetEmbedding.asset_id],
            set_={'content': content, 'embedding': embedding.tolist()},
        )
        await self._session.execute(statement)
        logger.info('Upserted asset embedding: asset_id=%d', asset_id)
