from typing import Any

import httpx
import numpy as np
from numpy.typing import NDArray

from infra.settings import get_settings

EMBEDDING_DIMENSION = 256
DEFAULT_MODEL = 'embeddinggemma-2:270m-q8_0-text'


class OllamaEmbeddingEngine:
    """Async text embedding client for Ollama's embed endpoint."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.OLLAMA_BASE_URL.rstrip('/')
        self._model_name = settings.OLLAMA_EMBEDDING_MODEL or DEFAULT_MODEL

    async def embedding_document(
        self, name: str, description: str
    ) -> NDArray[np.float32]:
        text = f'title: {name} | text: {description}'
        return await self._embed(text)

    async def embedding_query(self, query: str) -> NDArray[np.float32]:
        text = f'task: search result | query: {query}'
        return await self._embed(text)

    async def embedding_asset(
        self, name: str, description: str
    ) -> NDArray[np.float32]:
        text = f'title: {name} | text: {description}'
        return await self._embed(text)

    async def _embed(self, input_text: str) -> NDArray[np.float32]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f'{self._base_url}/api/embed',
                json={
                    'model': self._model_name,
                    'input': input_text,
                    'dimensions': EMBEDDING_DIMENSION,
                },
            )
        response.raise_for_status()
        return self._parse_embedding(response.json())

    @staticmethod
    def _parse_embedding(response_data: Any) -> NDArray[np.float32]:
        if not isinstance(response_data, dict):
            raise ValueError('Ollama embed response must be a JSON object')

        embeddings = response_data.get('embeddings')
        if not isinstance(embeddings, list) or len(embeddings) != 1:
            raise ValueError(
                'Ollama embed response must contain exactly one embedding'
            )

        try:
            vector = np.asarray(embeddings[0], dtype=np.float32)
        except (TypeError, ValueError) as error:
            raise ValueError(
                'Ollama embedding must contain numeric values'
            ) from error

        if vector.shape != (EMBEDDING_DIMENSION,):
            raise ValueError(
                f'Ollama embedding must have {EMBEDDING_DIMENSION} values; '
                f'got shape {vector.shape}'
            )
        if not np.isfinite(vector).all():
            raise ValueError('Ollama embedding contains non-finite values')

        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm == 0.0:
            raise ValueError(
                'Ollama embedding must have a finite non-zero norm'
            )

        return vector
