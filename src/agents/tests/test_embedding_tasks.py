from unittest.mock import AsyncMock, Mock

import pytest

from agents import tasks


@pytest.mark.parametrize(
    (
        'task',
        'use_case_name',
        'resource_id',
        'expected_name',
    ),
    [
        (
            tasks.embed_document_task,
            'embed_document',
            17,
            'agents.embeddings.document',
        ),
        (
            tasks.embed_asset_task,
            'embed_asset',
            28,
            'agents.embeddings.asset',
        ),
    ],
)
def test_celery_sync_entrypoint_runs_async_context(
    monkeypatch, task, use_case_name, resource_id, expected_name
):
    async_runner = Mock(return_value=True)
    monkeypatch.setattr(tasks.asyncio, 'run', async_runner)

    result = task.run(resource_id)

    assert result is True
    async_runner.assert_called_once()
    coroutine = async_runner.call_args.args[0]
    expected_context = (
        '_embed_document'
        if use_case_name == 'embed_document'
        else '_embed_asset'
    )
    assert coroutine.cr_code.co_name == (expected_context)
    coroutine.close()
    assert task.name == expected_name
    assert task.autoretry_for == (Exception,)
    assert task.retry_kwargs == {'max_retries': 8}


@pytest.mark.parametrize(
    ('async_context_name', 'use_case_name', 'resource_id'),
    [
        ('_embed_document', 'embed_document', 17),
        ('_embed_asset', 'embed_asset', 28),
    ],
)
@pytest.mark.asyncio
async def test_embedding_async_context_delegates_to_use_case(
    monkeypatch, async_context_name, use_case_name, resource_id
):
    agents_uow = AsyncMock()
    agents_uow.__aenter__.return_value = agents_uow
    project_client = object()
    engine = object()
    use_case = AsyncMock(return_value=True)
    monkeypatch.setattr(tasks, 'create_agents_unit_of_work', lambda: agents_uow)
    monkeypatch.setattr(tasks, 'create_project_client', lambda: project_client)
    monkeypatch.setattr(tasks, 'create_embedding_engine', lambda: engine)
    monkeypatch.setattr(tasks, use_case_name, use_case)

    result = await getattr(tasks, async_context_name)(resource_id)

    assert result is True
    use_case.assert_awaited_once_with(
        project_client, agents_uow, engine, resource_id
    )
    agents_uow.__aenter__.assert_awaited_once()
    agents_uow.__aexit__.assert_awaited_once()
