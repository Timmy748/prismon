import asyncio
import logging
from unittest.mock import AsyncMock

import numpy as np
import pytest

from agents.dtos.search import HybridSearchCandidate
from agents.llm_engine.base import GenerationResult
from agents.use_cases.rag_resources import LoadedResource
from agents.workflows.nodes import rag as rag_module
from agents.workflows.nodes.rag import (
    RAGInput,
    RAGNode,
    RelevanceDecision,
)

PROJECT_ID = 7
USER_ID = 9


@pytest.mark.asyncio
async def test_rag_node_rewrites_retrieves_loads_and_selects_typed_sources(
    monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger='agents.workflows.nodes.rag')
    embedding = np.array([0.1, 0.2], dtype=np.float32)
    embedding_engine = AsyncMock()
    embedding_engine.embedding_query.return_value = embedding
    engine = AsyncMock()

    async def generate(messages, system_prompt, *, output_schema=None):
        if output_schema is None:
            return GenerationResult(raw_text='focused search query')
        relevant = 'Useful asset source' in messages[0].text
        return GenerationResult(
            raw_text='',
            structured_output=RelevanceDecision(
                relevant=relevant,
                reason=(
                    'Contains useful handbook details'
                    if relevant
                    else 'Does not answer the handbook question'
                ),
            ),
        )

    engine.generate.side_effect = generate
    candidates = [
        HybridSearchCandidate('document', 20, 1, 0.02, 2, 1),
        HybridSearchCandidate('asset', 30, 2, 0.04, 1, 2),
        HybridSearchCandidate('document', 10, 3, 0.03, 3, 3),
    ]
    uow = AsyncMock()
    uow.document_embedding_repository.hybrid_search.return_value = [
        candidate
        for candidate in candidates
        if candidate.resource_type == 'document'
    ]
    uow.asset_embedding_repository.hybrid_search.return_value = [
        candidate
        for candidate in candidates
        if candidate.resource_type == 'asset'
    ]
    project_client = AsyncMock()
    loaded_resources = [
        LoadedResource('asset', 30, 1, 'text/markdown', 'Useful asset source'),
        LoadedResource('document', 20, 2, 'text/plain', 'Useful source'),
        LoadedResource('document', 10, 3, 'text/plain', 'Unrelated source'),
    ]

    async def load_candidates(
        candidates, loaded_project_client, project_id, user_id
    ):
        assert loaded_project_client is project_client
        assert project_id == PROJECT_ID
        assert user_id == USER_ID
        return loaded_resources

    monkeypatch.setattr(rag_module, 'load_rag_resources', load_candidates)
    node = RAGNode(
        engine, embedding_engine, uow, project_client, max_candidates=3
    )

    result = await node.run(RAGInput('What does the handbook say?', 7, 9))

    assert result.search_query == 'focused search query'
    assert [
        (item.resource_type, item.resource_id, item.rank)
        for item in result.candidates
    ] == [('asset', 30, 1), ('document', 10, 2), ('document', 20, 3)]
    assert [
        (item.resource_type, item.resource_id)
        for item in result.selected_sources
    ] == [('asset', 30)]
    assert result.context_text == '[asset 30]\nUseful asset source'
    embedding_engine.embedding_query.assert_awaited_once_with(
        'focused search query'
    )
    uow.document_embedding_repository.hybrid_search.assert_awaited_once_with(
        project_id=7,
        query='focused search query',
        query_embedding=embedding,
        limit=3,
        rrf_k=60,
    )
    uow.asset_embedding_repository.hybrid_search.assert_awaited_once_with(
        project_id=7,
        query='focused search query',
        query_embedding=embedding,
        limit=3,
        rrf_k=60,
    )
    relevance_messages = [
        call.args[0][0] for call in engine.generate.await_args_list[1:]
    ]
    assert len(relevance_messages) == len(candidates)
    assert all(message.payload == {} for message in relevance_messages)
    log_messages = [record.getMessage() for record in caplog.records]
    assert any(
        "search_query='focused search query'" in message
        for message in log_messages
    )
    assert any(
        "reason='Contains useful handbook details'" in message
        for message in log_messages
    )
    assert any(
        'RAG candidate rejected:' in message
        and 'resource_id=10' in message
        and 'Does not answer the handbook question' in message
        for message in log_messages
    )


@pytest.mark.asyncio
async def test_rag_node_evaluates_resource_relevance_in_parallel():
    candidate_count = 3
    active_evaluations = 0
    max_active_evaluations = 0

    async def evaluate_resource(*args, **kwargs):
        nonlocal active_evaluations, max_active_evaluations
        active_evaluations += 1
        max_active_evaluations = max(max_active_evaluations, active_evaluations)
        await asyncio.sleep(0)
        active_evaluations -= 1
        return GenerationResult(
            raw_text='',
            structured_output=RelevanceDecision(
                relevant=True, reason='Contains relevant text'
            ),
        )

    engine = AsyncMock()
    engine.generate.side_effect = evaluate_resource
    node = RAGNode(engine, AsyncMock(), AsyncMock(), AsyncMock())
    candidates = [
        HybridSearchCandidate('document', resource_id, rank, 0.02, 1, 1)
        for rank, resource_id in enumerate(
            range(1, candidate_count + 1), start=1
        )
    ]
    resources = [
        LoadedResource('document', resource_id, rank, 'text/plain', 'content')
        for rank, resource_id in enumerate(
            range(1, candidate_count + 1), start=1
        )
    ]

    selected = await node._select_sources(
        'question', candidates, resources, 'test-run'
    )

    assert max_active_evaluations == candidate_count
    assert [source.resource_id for source in selected] == [1, 2, 3]


@pytest.mark.asyncio
async def test_rag_node_returns_typed_run_result():
    engine = AsyncMock()
    engine.generate.return_value = GenerationResult(raw_text='rewritten')
    embedding_engine = AsyncMock()
    embedding_engine.embedding_query.return_value = np.array(
        [1], dtype=np.float32
    )
    uow = AsyncMock()
    uow.document_embedding_repository.hybrid_search.return_value = []
    uow.asset_embedding_repository.hybrid_search.return_value = []
    project_client = AsyncMock()
    node = RAGNode(
        engine=engine,
        embedding_engine=embedding_engine,
        uow=uow,
        project_client=project_client,
    )

    result = await node.run(RAGInput('Question?', 7, 9))

    assert result.context_text == ''
    assert result.search_query == 'rewritten'
    assert result.question == 'Question?'
    uow.document_embedding_repository.hybrid_search.assert_awaited_once_with(
        project_id=7,
        query='rewritten',
        query_embedding=embedding_engine.embedding_query.return_value,
        limit=8,
        rrf_k=60,
    )


@pytest.mark.asyncio
async def test_rag_node_falls_back_to_question_when_rewrite_fails():
    engine = AsyncMock()
    engine.generate.side_effect = RuntimeError('rewrite unavailable')
    embedding_engine = AsyncMock()
    embedding_engine.embedding_query.return_value = np.array(
        [1], dtype=np.float32
    )
    uow = AsyncMock()
    uow.document_embedding_repository.hybrid_search.return_value = []
    uow.asset_embedding_repository.hybrid_search.return_value = []
    node = RAGNode(engine, embedding_engine, uow, AsyncMock())

    result = await node.run(RAGInput('Original question', 7, 9))

    assert result.search_query == 'Original question'
    uow.document_embedding_repository.hybrid_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_rag_node_rejects_empty_question():
    node = RAGNode(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())

    with pytest.raises(ValueError, match='question must not be empty'):
        await node.run(RAGInput('  ', 7, 9))


def test_rag_node_rejects_zero_candidate_limit():
    with pytest.raises(
        ValueError, match='max_candidates must be greater than zero'
    ):
        RAGNode(
            AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock(), max_candidates=0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'resource',
    [
        None,
        LoadedResource('document', 1, 1, 'text/plain', 'text', error='failed'),
        LoadedResource('document', 1, 1, 'text/plain', '  '),
    ],
    ids=['missing', 'load-error', 'blank-text'],
)
async def test_rag_node_skips_unusable_loaded_resources(resource):
    candidate = HybridSearchCandidate('document', 1, 1, 0.1)
    node = RAGNode(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())

    selected = await node._select_source('question', candidate, resource, 'run')

    assert selected is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response',
    [RuntimeError('model failed'), GenerationResult(raw_text='')],
)
async def test_rag_node_skips_sources_when_relevance_is_unavailable(
    response,
):
    engine = AsyncMock()
    if isinstance(response, Exception):
        engine.generate.side_effect = response
    else:
        engine.generate.return_value = response
    node = RAGNode(engine, AsyncMock(), AsyncMock(), AsyncMock())
    candidate = HybridSearchCandidate('document', 1, 1, 0.1)
    resource = LoadedResource('document', 1, 1, 'text/plain', 'content')

    assert (
        await node._select_source('question', candidate, resource, 'run')
        is None
    )


@pytest.mark.asyncio
async def test_rag_node_reraises_embedding_and_search_errors(monkeypatch):
    engine = AsyncMock()
    engine.generate.return_value = GenerationResult(raw_text='question')
    broken_embedding = AsyncMock()
    broken_embedding.embedding_query.side_effect = RuntimeError('embedding')
    node = RAGNode(engine, broken_embedding, AsyncMock(), AsyncMock())
    with pytest.raises(RuntimeError, match='embedding'):
        await node.run(RAGInput('question', 7, 9))

    embedding = AsyncMock()
    embedding.embedding_query.return_value = np.array([1], dtype=np.float32)
    uow = AsyncMock()
    uow.document_embedding_repository.hybrid_search.side_effect = RuntimeError(
        'search'
    )
    node = RAGNode(engine, embedding, uow, AsyncMock())
    with pytest.raises(RuntimeError, match='search'):
        await node.run(RAGInput('question', 7, 9))


@pytest.mark.asyncio
async def test_rag_node_reraises_resource_loading_errors(monkeypatch):
    engine = AsyncMock()
    engine.generate.return_value = GenerationResult(raw_text='question')
    embedding = AsyncMock()
    embedding.embedding_query.return_value = np.array([1], dtype=np.float32)
    uow = AsyncMock()
    uow.document_embedding_repository.hybrid_search.return_value = []
    uow.asset_embedding_repository.hybrid_search.return_value = []
    monkeypatch.setattr(
        rag_module,
        'load_rag_resources',
        AsyncMock(side_effect=RuntimeError('resource loading')),
    )
    node = RAGNode(engine, embedding, uow, AsyncMock())

    with pytest.raises(RuntimeError, match='resource loading'):
        await node.run(RAGInput('question', 7, 9))
