from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class IEmbeddingEngine(Protocol):
    async def embedding_document(
        self, name: str, description: str
    ) -> NDArray[np.float32]:
        """Return a normalized embedding for a document."""
        ...

    async def embedding_query(self, query: str) -> NDArray[np.float32]:
        """Return a normalized embedding for a text search query."""
        ...

    async def embedding_asset(
        self, name: str, description: str
    ) -> NDArray[np.float32]:
        """Return a normalized text embedding for an asset's metadata."""
        ...
