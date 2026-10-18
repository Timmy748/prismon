from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

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
    bound_llm = MagicMock()
    llm.bind_tools.return_value = bound_llm
    llm.ainvoke = AsyncMock(return_value=AIMessage(content='model answer'))

    async def stream_chunks(*args, **kwargs):
        yield AIMessage(content='first ')
        yield AIMessage(content='')
        yield AIMessage(content='last')

    llm.astream = MagicMock(side_effect=stream_chunks)
    structured_llm = MagicMock()
    structured_llm.ainvoke = AsyncMock(return_value={'result': 'structured'})
    llm.with_structured_output.return_value = structured_llm
    return SimpleNamespace(
        llm=llm,
        bound_llm=bound_llm,
        structured_llm=structured_llm,
    )


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
