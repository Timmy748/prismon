from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agents.entities.document_embedding import DocumentEmbedding
from infra.logs import get_logger

logger = get_logger(__name__)


class IDocumentEmbeddingRepository(Protocol):
    async def upsert_embedding(
        self,
        document_id: int,
        content: str,
        embedding: NDArray[np.float32],
    ) -> None: ...


class DocumentEmbeddingRepository(IDocumentEmbeddingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_embedding(
        self,
        document_id: int,
        content: str,
        embedding: NDArray[np.float32],
    ) -> None:
        statement = insert(DocumentEmbedding).values(
            document_id=document_id,
            content=content,
            embedding=embedding.tolist(),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[DocumentEmbedding.document_id],
            set_={'content': content, 'embedding': embedding.tolist()},
        )
        await self._session.execute(statement)
        logger.info('Upserted document embedding: document_id=%d', document_id)
