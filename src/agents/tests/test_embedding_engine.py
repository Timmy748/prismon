import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest

from agents.embedding_engine.ollama import OllamaEmbeddingEngine

EMBEDDING_DIMENSION = 256
VALID_EMBEDDING = [0.6, 0.8, *([0.0] * (EMBEDDING_DIMENSION - 2))]


@asynccontextmanager
async def _engine_with_response(
    monkeypatch: pytest.MonkeyPatch,
    response_data: Any,
    status_code: int = 200,
):
    requests: list[httpx.Request] = []
    clients: list[httpx.AsyncClient] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status_code,
            content=json.dumps(response_data, allow_nan=True),
            headers={'content-type': 'application/json'},
        )

    monkeypatch.setattr(
        'agents.embedding_engine.ollama.get_settings',
        lambda: SimpleNamespace(
            OLLAMA_BASE_URL='http://ollama.test:11434/',
            OLLAMA_EMBEDDING_MODEL='embeddinggemma2-test',
        ),
    )
    async_client_class = httpx.AsyncClient

    def client_factory(*args, **kwargs) -> httpx.AsyncClient:
        client = async_client_class(
            *args, transport=httpx.MockTransport(handler), **kwargs
        )
        clients.append(client)
        return client

    monkeypatch.setattr(
        'agents.embedding_engine.ollama.httpx.AsyncClient', client_factory
    )
    yield OllamaEmbeddingEngine(), requests, clients


def _assert_embedding_contract(embedding: np.ndarray) -> None:
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (EMBEDDING_DIMENSION,)
    assert embedding.dtype == np.float32
    assert np.linalg.norm(embedding) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_embedding_document_sends_title_and_description(monkeypatch):
    async with _engine_with_response(
        monkeypatch, {'embeddings': [VALID_EMBEDDING]}
    ) as (engine, requests, _):
        embedding = await engine.embedding_document(
            'Manual de instalação', 'Instruções para instalar o produto.'
        )

    request = requests[0]
    payload = json.loads(request.content)
    assert request.method == 'POST'
    assert str(request.url) == 'http://ollama.test:11434/api/embed'
    assert payload == {
        'model': 'embeddinggemma2-test',
        'dimensions': EMBEDDING_DIMENSION,
        'input': (
            'title: Manual de instalação | '
            'text: Instruções para instalar o produto.'
        ),
    }
    _assert_embedding_contract(embedding)


@pytest.mark.asyncio
async def test_embedding_query_sends_search_query_prefix(monkeypatch):
    async with _engine_with_response(
        monkeypatch, {'embeddings': [VALID_EMBEDDING]}
    ) as (engine, requests, _):
        embedding = await engine.embedding_query('Como instalar o produto?')

    payload = json.loads(requests[0].content)
    assert payload['input'] == (
        'task: search result | query: Como instalar o produto?'
    )
    assert payload['dimensions'] == EMBEDDING_DIMENSION
    _assert_embedding_contract(embedding)


@pytest.mark.asyncio
async def test_embedding_asset_sends_only_text_metadata(monkeypatch):
    async with _engine_with_response(
        monkeypatch, {'embeddings': [VALID_EMBEDDING]}
    ) as (engine, requests, _):
        embedding = await engine.embedding_asset(
            'Produto vermelho', 'Foto frontal do produto.'
        )

    payload = json.loads(requests[0].content)
    assert payload['input'] == (
        'title: Produto vermelho | text: Foto frontal do produto.'
    )
    assert isinstance(payload['input'], str)
    assert 'image' not in payload
    assert payload['dimensions'] == EMBEDDING_DIMENSION
    _assert_embedding_contract(embedding)


@pytest.mark.asyncio
async def test_embedding_raises_for_ollama_api_error(monkeypatch):
    async with _engine_with_response(
        monkeypatch,
        {'error': 'model unavailable'},
        status_code=503,
    ) as (engine, _, _):
        with pytest.raises(httpx.HTTPStatusError):
            await engine.embedding_query('consulta')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response_data',
    [
        {},
        {'embeddings': []},
        {'embeddings': [VALID_EMBEDDING, VALID_EMBEDDING]},
    ],
    ids=['missing', 'empty', 'multiple'],
)
async def test_embedding_rejects_missing_or_multiple_vectors(
    monkeypatch, response_data
):
    async with _engine_with_response(monkeypatch, response_data) as (
        engine,
        _,
        _,
    ):
        with pytest.raises(ValueError, match='exactly one embedding'):
            await engine.embedding_query('consulta')


@pytest.mark.asyncio
async def test_embedding_rejects_wrong_dimension(monkeypatch):
    malformed_embedding = VALID_EMBEDDING[:-1]
    async with _engine_with_response(
        monkeypatch, {'embeddings': [malformed_embedding]}
    ) as (engine, _, _):
        with pytest.raises(ValueError, match='must have 256 values'):
            await engine.embedding_query('consulta')


@pytest.mark.asyncio
@pytest.mark.parametrize('invalid_value', [float('nan'), float('inf')])
async def test_embedding_rejects_non_finite_values(monkeypatch, invalid_value):
    malformed_embedding = [*VALID_EMBEDDING]
    malformed_embedding[0] = invalid_value
    async with _engine_with_response(
        monkeypatch, {'embeddings': [malformed_embedding]}
    ) as (engine, _, _):
        with pytest.raises(ValueError, match='non-finite'):
            await engine.embedding_query('consulta')


@pytest.mark.asyncio
async def test_embedding_rejects_zero_norm(monkeypatch):
    zero_embedding = [0.0] * EMBEDDING_DIMENSION
    async with _engine_with_response(
        monkeypatch, {'embeddings': [zero_embedding]}
    ) as (engine, _, _):
        with pytest.raises(ValueError, match='non-zero norm'):
            await engine.embedding_query('consulta')


@pytest.mark.asyncio
async def test_embedding_closes_http_client_after_request(monkeypatch):
    async with _engine_with_response(
        monkeypatch, {'embeddings': [VALID_EMBEDDING]}
    ) as (engine, _, clients):
        await engine.embedding_query('consulta')

    assert len(clients) == 1
    assert clients[0].is_closed


def test_embedding_rejects_non_object_ollama_response():
    with pytest.raises(ValueError, match='must be a JSON object'):
        OllamaEmbeddingEngine._parse_embedding([])


def test_embedding_rejects_non_numeric_ollama_vector():
    with pytest.raises(ValueError, match='numeric values'):
        OllamaEmbeddingEngine._parse_embedding({'embeddings': [['invalid']]})
