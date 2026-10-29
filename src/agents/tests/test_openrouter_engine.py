from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from agents.llm_engine.base import GenerationChunk, GenerationFinal
from agents.llm_engine.openrouter import OpenRouterEngine


def test_constructor_configures_chat_openrouter(monkeypatch):
    settings = SimpleNamespace(
        OPENROUTER_MODEL='provider/model',
        OPENROUTER_TEMPERATURE=0.4,
    )
    chat_openrouter = MagicMock()
    factory = MagicMock(return_value=chat_openrouter)
    monkeypatch.setattr(
        'agents.llm_engine.openrouter.get_settings', lambda: settings
    )
    monkeypatch.setattr('agents.llm_engine.openrouter.ChatOpenRouter', factory)

    engine = OpenRouterEngine(api_key='test-key')

    factory.assert_called_once_with(
        api_key='test-key',
        model='provider/model',
        temperature=0.4,
        stream_usage=True,
    )
    assert engine._llm is chat_openrouter


@pytest.mark.parametrize('api_key', ['', '   '])
def test_constructor_rejects_missing_api_key(monkeypatch, api_key):
    settings = SimpleNamespace(
        OPENROUTER_MODEL='provider/model',
        OPENROUTER_TEMPERATURE=0.4,
    )
    monkeypatch.setattr(
        'agents.llm_engine.openrouter.get_settings',
        lambda: settings,
    )

    with pytest.raises(ValueError, match='API key must be provided'):
        OpenRouterEngine(api_key=api_key)


def test_constructor_rejects_missing_model(monkeypatch):
    settings = SimpleNamespace(
        OPENROUTER_MODEL='  ',
        OPENROUTER_TEMPERATURE=0.4,
    )
    monkeypatch.setattr(
        'agents.llm_engine.openrouter.get_settings',
        lambda: settings,
    )

    with pytest.raises(ValueError, match='OPENROUTER_MODEL'):
        OpenRouterEngine(api_key='test-key')


def test_metadata_preserves_usage_metadata_and_openrouter_fields():
    llm = SimpleNamespace(model_name='configured-model', model='fallback')
    response = AIMessage(
        content='answer',
        usage_metadata={
            'input_tokens': 6,
            'output_tokens': 8,
            'total_tokens': 14,
        },
        response_metadata={
            'model_name': 'response-model',
            'model': 'other-model',
            'finish_reason': 'stop',
            'stop_reason': 'fallback-stop',
            'token_usage': {
                'prompt_tokens': 60,
                'completion_tokens': 80,
                'total_tokens': 140,
            },
        },
    )

    metadata = OpenRouterEngine._metadata(llm, response, 2.0)

    assert (
        metadata.model,
        metadata.input_tokens,
        metadata.output_tokens,
        metadata.total_tokens,
        metadata.elapsed_seconds,
        metadata.tokens_per_second,
        metadata.finish_reason,
    ) == ('response-model', 6, 8, 14, 2.0, 4.0, 'stop')


def test_metadata_uses_openrouter_token_usage_and_derives_total():
    llm = SimpleNamespace()
    response = AIMessage(
        content='answer',
        response_metadata={
            'model': 'response-model',
            'stop_reason': 'length',
            'token_usage': {'prompt_tokens': 3, 'completion_tokens': 5},
        },
    )

    metadata = OpenRouterEngine._metadata(llm, response, 2.0)

    assert (
        metadata.model,
        metadata.input_tokens,
        metadata.output_tokens,
        metadata.total_tokens,
        metadata.elapsed_seconds,
        metadata.tokens_per_second,
        metadata.finish_reason,
    ) == ('response-model', 3, 5, 8, 2.0, 2.5, 'length')


@pytest.mark.parametrize(
    ('llm', 'expected_model'),
    [
        (SimpleNamespace(model_name='configured-name'), 'configured-name'),
        (SimpleNamespace(model='configured-model'), 'configured-model'),
        (SimpleNamespace(), None),
    ],
)
def test_metadata_falls_back_to_llm_model_and_handles_absent_usage(
    llm, expected_model
):
    response = AIMessage(
        content='answer',
        response_metadata={
            'model_name': '',
            'model': '',
            'token_usage': 'malformed',
        },
    )

    metadata = OpenRouterEngine._metadata(llm, response, 0.0)

    assert (
        metadata.model,
        metadata.input_tokens,
        metadata.output_tokens,
        metadata.total_tokens,
        metadata.elapsed_seconds,
        metadata.tokens_per_second,
        metadata.finish_reason,
    ) == (expected_model, None, None, None, 0.0, None, None)


def test_tool_calls_skips_invalid_provider_calls():
    response = SimpleNamespace(
        tool_calls=[
            object(),
            {'name': None, 'args': {}},
            {'name': 'lookup_weather', 'args': []},
        ]
    )

    assert OpenRouterEngine._tool_calls(response) == []


def test_tool_call_deltas_skips_chunks_without_valid_index():
    chunk = AIMessageChunk(
        content='',
        tool_call_chunks=[
            {'name': 'lookup_weather', 'args': '{}', 'id': 'call-1'}
        ],
    )

    assert OpenRouterEngine._tool_call_deltas(chunk) == []


@pytest.mark.asyncio
async def test_generate_uses_inherited_openrouter_chat_contract(
    message_history,
):
    llm = MagicMock()
    llm.model = 'test-model'
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='OpenRouter response',
            usage_metadata={
                'input_tokens': 4,
                'output_tokens': 6,
                'total_tokens': 10,
            },
            response_metadata={
                'model': 'provider/model',
                'finish_reason': 'stop',
            },
        )
    )
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    result = await engine.generate(message_history, 'system prompt')

    assert result.raw_text == 'OpenRouter response'
    assert result.usage.model == 'provider/model'
    assert (
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.total_tokens,
    ) == (4, 6, 10)
    llm.ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_passes_through_structured_output(
    message_history, mock_ollama_llm
):
    engine = OpenRouterEngine(api_key='test-key', llm=mock_ollama_llm.llm)

    result = await engine.generate(
        message_history, 'system prompt', output_schema=dict
    )

    assert result.structured_output == {'result': 'structured'}
    assert result.raw_text == '{"result": "structured"}'


@pytest.mark.asyncio
async def test_generate_passes_through_tool_calls(
    message_history, mock_ollama_tool_call_llm, sample_tool
):
    engine = OpenRouterEngine(
        api_key='test-key', llm=mock_ollama_tool_call_llm.llm
    )

    result = await engine.generate(
        message_history, 'system prompt', tools=[sample_tool]
    )

    assert result.tool_calls[0].name == 'lookup_weather'
    assert result.tool_calls[0].args == {'city': 'Paris'}


@pytest.mark.asyncio
async def test_generate_propagates_provider_error(message_history):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError('provider unavailable'))
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    with pytest.raises(RuntimeError, match='provider unavailable'):
        await engine.generate(message_history, 'system prompt')


@pytest.mark.asyncio
async def test_generate_rejects_non_mapping_structured_envelope(
    message_history,
):
    llm = MagicMock()
    runnable = SimpleNamespace(ainvoke=AsyncMock(return_value='invalid'))
    llm.with_structured_output.return_value = runnable
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    with pytest.raises(TypeError, match='invalid envelope'):
        await engine.generate(message_history, 'prompt', output_schema=dict)


@pytest.mark.asyncio
async def test_generate_raises_structured_parse_error(message_history):
    parsing_error = ValueError('schema mismatch')
    llm = MagicMock()
    runnable = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value={
                'parsed': None,
                'raw': AIMessage(content='invalid json'),
                'parsing_error': parsing_error,
            }
        )
    )
    llm.with_structured_output.return_value = runnable
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    with pytest.raises(ValueError, match='parsing failed') as error:
        await engine.generate(message_history, 'prompt', output_schema=dict)

    assert error.value.__cause__ is parsing_error


@pytest.mark.asyncio
async def test_generate_rejects_non_message_provider_response(message_history):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value='invalid')
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    with pytest.raises(TypeError, match='invalid message'):
        await engine.generate(message_history, 'prompt')


@pytest.mark.asyncio
async def test_stream_returns_text_and_complete_usage_metadata(
    message_history,
):
    llm = MagicMock()
    llm.model = 'test-model'

    async def stream_chunks(*args, **kwargs):
        yield AIMessage(content='not a streaming chunk')
        yield AIMessageChunk(content='first ')
        yield AIMessageChunk(
            content='last',
            usage_metadata={
                'input_tokens': 8,
                'output_tokens': 20,
                'total_tokens': 28,
            },
            response_metadata={
                'model_name': 'test-model',
                'finish_reason': 'stop',
            },
        )

    llm.astream = MagicMock(side_effect=stream_chunks)
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]
    text = ''.join(
        event.text_delta
        for event in events
        if isinstance(event, GenerationChunk)
    )
    final = next(
        event for event in events if isinstance(event, GenerationFinal)
    )

    assert text == 'first last'
    assert final.raw_text == 'first last'
    assert final.usage.model == 'test-model'
    assert (
        final.usage.input_tokens,
        final.usage.output_tokens,
        final.usage.total_tokens,
    ) == (8, 20, 28)
    assert final.usage.tokens_per_second is not None
    assert final.usage.finish_reason == 'stop'


@pytest.mark.asyncio
async def test_stream_returns_empty_final_when_provider_emits_no_chunks(
    message_history,
):
    llm = MagicMock()

    async def stream_no_chunks(*args, **kwargs):
        if False:
            yield AIMessageChunk(content='unreachable')

    llm.astream = MagicMock(side_effect=stream_no_chunks)
    engine = OpenRouterEngine(api_key='test-key', llm=llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]

    assert len(events) == 1
    assert isinstance(events[0], GenerationFinal)
    assert events[0].raw_text == ''
    assert events[0].tool_calls == []


@pytest.mark.asyncio
async def test_stream_passes_through_tool_call_deltas(
    message_history, mock_ollama_tool_call_llm, sample_tool
):
    engine = OpenRouterEngine(
        api_key='test-key', llm=mock_ollama_tool_call_llm.llm
    )

    events = [
        event
        async for event in engine.stream(
            message_history, 'prompt', tools=[sample_tool]
        )
    ]

    assert events[0].tool_call_delta.name == 'lookup_weather'
    final = next(
        event for event in events if isinstance(event, GenerationFinal)
    )
    assert final.tool_calls[0].args == {'city': 'Paris'}
