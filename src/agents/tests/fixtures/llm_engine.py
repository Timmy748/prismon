from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.runnables import RunnableLambda

from agents.dtos.message import MessageDTO
from agents.entities.message import SenderType


@pytest.fixture
def message_history():
    now = datetime.now(UTC)
    return [
        MessageDTO(
            id=1,
            chat_id=1,
            parent_id=None,
            sender_type=SenderType.USER,
            text='user question',
            payload={'ignored': 'user payload'},
            meta_data={},
            created_at=now,
            updated_at=now,
        ),
        MessageDTO(
            id=2,
            chat_id=1,
            parent_id=1,
            sender_type=SenderType.ASSISTANT,
            text='previous answer',
            payload={'ignored': 'assistant payload'},
            meta_data={},
            created_at=now,
            updated_at=now,
        ),
    ]


@pytest.fixture
def mock_ollama_llm():
    llm = MagicMock()
    llm.model = 'test-model'
    bound_llm = MagicMock()
    llm.bind_tools.return_value = bound_llm
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='model answer',
            usage_metadata={
                'input_tokens': 8,
                'output_tokens': 20,
                'total_tokens': 28,
            },
            response_metadata={
                'model': 'test-model',
                'total_duration': 2_000_000_000,
                'prompt_eval_count': 8,
                'eval_count': 20,
                'eval_duration': 1_000_000_000,
                'done_reason': 'stop',
            },
        )
    )

    async def stream_chunks(*args, **kwargs):
        yield AIMessageChunk(content='first ')
        yield AIMessageChunk(content='')
        yield AIMessageChunk(content='last')
        yield AIMessageChunk(
            content='',
            usage_metadata={
                'input_tokens': 8,
                'output_tokens': 20,
                'total_tokens': 28,
            },
            response_metadata={
                'model': 'test-model',
                'total_duration': 2_000_000_000,
                'prompt_eval_count': 8,
                'eval_count': 20,
                'eval_duration': 1_000_000_000,
                'done_reason': 'stop',
            },
        )

    llm.astream = MagicMock(side_effect=stream_chunks)
    structured_result = {
        'parsed': {'result': 'structured'},
        'raw': AIMessage(
            content='{"result": "structured"}',
            usage_metadata={
                'input_tokens': 8,
                'output_tokens': 20,
                'total_tokens': 28,
            },
            response_metadata={
                'model': 'test-model',
                'total_duration': 2_000_000_000,
                'prompt_eval_count': 8,
                'eval_count': 20,
                'eval_duration': 1_000_000_000,
                'done_reason': 'stop',
            },
        ),
        'parsing_error': None,
    }
    structured_llm = RunnableLambda(lambda _: structured_result)
    llm.with_structured_output = MagicMock(return_value=structured_llm)
    return SimpleNamespace(
        llm=llm,
        bound_llm=bound_llm,
        structured_llm=structured_llm,
    )


@pytest.fixture
def mock_ollama_tool_call_llm(mock_ollama_llm):
    mock_ollama_llm.bound_llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='',
            tool_calls=[
                {
                    'name': 'lookup_weather',
                    'args': {'city': 'Paris'},
                    'id': 'call-1',
                }
            ],
        )
    )

    async def stream_tool_call(*args, **kwargs):
        yield AIMessageChunk(
            content='Checking ',
            tool_call_chunks=[
                {
                    'name': 'lookup_weather',
                    'args': '{"city":',
                    'id': 'call-1',
                    'index': 0,
                }
            ],
        )
        yield AIMessageChunk(
            content='the weather',
            tool_call_chunks=[
                {
                    'name': None,
                    'args': '"Paris"}',
                    'id': None,
                    'index': 0,
                }
            ],
        )

    mock_ollama_llm.bound_llm.astream = MagicMock(side_effect=stream_tool_call)
    return mock_ollama_llm


@pytest.fixture
def ollama_settings():
    return SimpleNamespace(
        OLLAMA_BASE_URL='http://ollama:11434',
        OLLAMA_MODEL='test-model',
        OLLAMA_TEMPERATURE=0.25,
    )


@pytest.fixture
def sample_tool():
    def lookup_weather(city: str) -> str:
        """Look up the weather in a city."""
        return f'Weather in {city}'

    return lookup_weather
