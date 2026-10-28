from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import agents.use_cases.chats as chat_use_cases
from agents.dtos.message import CreateMessageDTO
from agents.entities.message import SenderType
from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
    GenerationMetadata,
)


@pytest.fixture
def workflow_stub(monkeypatch):
    generated = CreateMessageDTO(
        None,
        SenderType.ASSISTANT,
        'answer',
        {'generated': True},
        {'workflow': 'chat'},
    )
    workflow = AsyncMock()
    workflow.name = 'chat'
    workflow.version = '1'

    async def stream(*args, **kwargs):
        yield GenerationChunk(text_delta='ans')
        yield GenerationChunk(text_delta='wer')
        yield GenerationFinal(
            raw_text=generated.text,
            tool_calls=[],
            usage=GenerationMetadata(model='test-model'),
        )

    workflow.stream = Mock(side_effect=stream)
    registry = Mock()
    registry.get_workflow.return_value = workflow
    engine = object()
    monkeypatch.setattr(
        chat_use_cases,
        'workflow_registry_factory',
        Mock(return_value=registry),
    )
    monkeypatch.setattr(
        chat_use_cases, 'create_llm_engine', Mock(return_value=engine)
    )
    return SimpleNamespace(
        generated=generated,
        workflow=workflow,
        registry=registry,
        engine=engine,
    )


@pytest.fixture
def chat_workflow_engine(monkeypatch):
    engine = Mock()

    async def stream(*args, **kwargs):
        yield GenerationChunk(text_delta='model ')
        yield GenerationChunk(text_delta='answer')
        yield GenerationFinal(
            raw_text='model answer',
            tool_calls=[],
            usage=GenerationMetadata(
                model='test-model',
                input_tokens=8,
                output_tokens=20,
                total_tokens=28,
                elapsed_seconds=2.0,
                tokens_per_second=10.0,
                finish_reason='stop',
            ),
        )

    engine.stream = Mock(side_effect=stream)
    monkeypatch.setattr(
        chat_use_cases, 'create_llm_engine', Mock(return_value=engine)
    )
    return engine
