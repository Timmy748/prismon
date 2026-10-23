import pytest
from langgraph.graph.state import CompiledStateGraph

from agents.dtos.message import CreateMessageDTO
from agents.entities.message import SenderType
from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
)
from agents.workflows.base import WorkflowExecution
from agents.workflows.chat import ChatWorkflow


@pytest.mark.asyncio
async def test_chat_workflow_returns_generated_text(
    chat_workflow_engine, message_history
):
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    result = await workflow.run('thread-1', {'messages': message_history})

    assert result.text == 'model answer'
    assert result.parent_id is None


@pytest.mark.asyncio
async def test_chat_workflow_persists_generation_metadata(
    chat_workflow_engine, message_history
):
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    result = await workflow.run('thread-1', {'messages': message_history})

    assert result.meta_data == {
        'workflow': 'chat',
        'version': '1',
        'model': 'test-model',
        'input_tokens': 8,
        'output_tokens': 20,
        'total_tokens': 28,
        'elapsed_seconds': 2.0,
        'tokens_per_second': 10.0,
        'finish_reason': 'stop',
    }


@pytest.mark.asyncio
async def test_chat_workflow_resume_returns_generated_text(
    chat_workflow_engine, message_history
):
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    result = await workflow.resume('thread-1', {'messages': message_history})

    assert result.text == 'model answer'


@pytest.mark.asyncio
async def test_chat_workflow_stream_emits_chunks_then_final_generation(
    chat_workflow_engine, message_history
):
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    events = [
        event
        async for event in workflow.stream(
            'thread-1', {'messages': message_history}
        )
    ]

    chunks = [
        event.text_delta
        for event in events
        if isinstance(event, GenerationChunk)
    ]

    assert chunks == [
        'model ',
        'answer',
    ]
    assert isinstance(events[-1], GenerationFinal)
    assert events[-1].raw_text == 'model answer'


def test_chat_workflow_builds_compiled_graph(chat_workflow_engine):
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    assert isinstance(workflow.graph, CompiledStateGraph)
    assert workflow.graph is workflow.graph


@pytest.mark.asyncio
async def test_workflow_execution_default_stream_yields_run_result():
    result = CreateMessageDTO(None, SenderType.ASSISTANT, 'answer', {}, {})

    class LegacyWorkflow(WorkflowExecution):
        async def run(self, thread_id, input):
            return result

        async def resume(self, thread_id, input):
            return result

        def _build_graph(self):
            return None

    workflow = LegacyWorkflow(engine=None)

    events = [event async for event in workflow.stream('thread-1', {})]

    assert events == [result]


@pytest.mark.asyncio
async def test_chat_workflow_run_rejects_engine_stream_without_final(
    chat_workflow_engine, message_history
):
    async def chunks_only(*args, **kwargs):
        yield GenerationChunk(text_delta='partial')

    chat_workflow_engine.stream.side_effect = chunks_only
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    with pytest.raises(RuntimeError, match='without a final generation'):
        await workflow.run('thread-1', {'messages': message_history})


@pytest.mark.asyncio
async def test_chat_workflow_run_rejects_stream_without_final_event(
    chat_workflow_engine, message_history
):
    workflow = ChatWorkflow(engine=chat_workflow_engine)

    async def chunks_only(*args, **kwargs):
        yield GenerationChunk(text_delta='partial')

    workflow.stream = chunks_only

    with pytest.raises(RuntimeError, match='finished without a final'):
        await workflow.run('thread-1', {'messages': message_history})
