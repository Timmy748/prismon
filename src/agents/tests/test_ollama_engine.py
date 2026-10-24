import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
)

from agents.llm_engine.base import (
    GenerationChunk,
    GenerationFinal,
    ToolCall,
    ToolCallDelta,
)
from agents.llm_engine.ollama import OllamaEngine

EXPECTED_OUTPUT_TOKENS = 20
EXPECTED_TOTAL_TOKENS_FROM_METADATA = 7
EXPECTED_TOKENS_PER_SECOND = 20.0


@pytest.mark.asyncio
async def test_generate_logs_and_reraises_model_error(
    mock_ollama_llm, message_history, caplog
):
    mock_ollama_llm.llm.ainvoke = AsyncMock(
        side_effect=RuntimeError('model unavailable')
    )
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    with caplog.at_level(logging.ERROR, logger='agents.llm_engine.ollama'):
        with pytest.raises(RuntimeError, match='model unavailable'):
            await engine.generate(message_history, 'system instructions')

    assert 'LLM generation failed: error_type=RuntimeError' in caplog.text


def test_constructor_configures_chat_ollama(monkeypatch, ollama_settings):
    chat_ollama = MagicMock()
    factory = MagicMock(return_value=chat_ollama)
    monkeypatch.setattr(
        'agents.llm_engine.ollama.get_settings', lambda: ollama_settings
    )
    monkeypatch.setattr('agents.llm_engine.ollama.ChatOllama', factory)

    OllamaEngine()

    factory.assert_called_once_with(
        base_url='http://ollama:11434', model='test-model', temperature=0.25
    )


@pytest.mark.asyncio
async def test_generate_returns_text_and_metadata(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    result = await engine.generate(message_history, 'system instructions')

    assert (result.raw_text, result.structured_output, result.usage.model) == (
        'model answer',
        None,
        'test-model',
    )


@pytest.mark.asyncio
async def test_generate_reports_token_usage(mock_ollama_llm, message_history):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    result = await engine.generate(message_history, 'system instructions')

    assert (
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.total_tokens,
    ) == (8, EXPECTED_OUTPUT_TOKENS, 28)


@pytest.mark.asyncio
async def test_generate_reports_generation_rate(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    result = await engine.generate(message_history, 'system instructions')

    assert result.usage.tokens_per_second == EXPECTED_TOKENS_PER_SECOND


@pytest.mark.asyncio
async def test_generate_derives_total_tokens_from_response_metadata(
    mock_ollama_llm, message_history
):
    mock_ollama_llm.llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content='model answer',
            response_metadata={'prompt_eval_count': 3, 'eval_count': 4},
        )
    )
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    result = await engine.generate(message_history, 'prompt')

    assert result.usage.total_tokens == EXPECTED_TOTAL_TOKENS_FROM_METADATA


@pytest.mark.asyncio
async def test_generate_passes_runnable_config(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    await engine.generate(
        message_history, 'system instructions', temperature=0.5
    )

    mock_ollama_llm.llm.ainvoke.assert_awaited_once_with(
        [
            SystemMessage(content='system instructions'),
            HumanMessage(content='user question'),
            AIMessage(content='previous answer'),
        ],
        temperature=0.5,
    )


@pytest.mark.asyncio
async def test_generate_binds_tools_for_this_call(
    mock_ollama_tool_call_llm, message_history, sample_tool
):
    engine = OllamaEngine(llm=mock_ollama_tool_call_llm.llm)

    await engine.generate(message_history, 'prompt', tools=[sample_tool])

    mock_ollama_tool_call_llm.llm.bind_tools.assert_called_once_with(
        [sample_tool]
    )


@pytest.mark.asyncio
async def test_generate_returns_normalized_tool_calls(
    mock_ollama_tool_call_llm, message_history, sample_tool
):
    engine = OllamaEngine(llm=mock_ollama_tool_call_llm.llm)

    result = await engine.generate(
        message_history, 'prompt', tools=[sample_tool]
    )

    assert result.tool_calls == [
        ToolCall('call-1', 'lookup_weather', {'city': 'Paris'})
    ]


def test_tool_calls_skips_non_mapping_entries():
    response = SimpleNamespace(tool_calls=[object()])

    calls = OllamaEngine._tool_calls(response)

    assert calls == []


def test_metadata_avoids_zero_duration_generation_rate():
    response = AIMessage(
        content='answer',
        usage_metadata={
            'input_tokens': 2,
            'output_tokens': 1,
            'total_tokens': 3,
        },
    )

    metadata = OllamaEngine._metadata(
        MagicMock(), response, elapsed_seconds=0.0
    )

    assert metadata.tokens_per_second is None


def test_tool_calls_skips_entries_with_invalid_name_or_arguments():
    response = SimpleNamespace(
        tool_calls=[
            {'name': None, 'args': {}},
            {'name': 'lookup_weather', 'args': []},
        ]
    )

    calls = OllamaEngine._tool_calls(response)

    assert calls == []


def test_tool_call_deltas_skips_entries_without_integer_index():
    chunk = AIMessageChunk(
        content='',
        tool_call_chunks=[
            {'name': 'lookup_weather', 'args': '{}', 'id': 'call-1'}
        ],
    )

    deltas = OllamaEngine._tool_call_deltas(chunk)

    assert deltas == []


@pytest.mark.asyncio
async def test_generate_structured_returns_parsed_schema(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    result = await engine.generate(
        message_history, 'system instructions', output_schema=dict
    )

    assert result.structured_output == {'result': 'structured'}


@pytest.mark.asyncio
async def test_generate_structured_keeps_raw_text(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    result = await engine.generate(
        message_history, 'system instructions', output_schema=dict
    )

    assert result.raw_text == '{"result": "structured"}'


@pytest.mark.asyncio
async def test_generate_structured_requests_raw_response(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    await engine.generate(message_history, 'prompt', output_schema=dict)

    mock_ollama_llm.llm.with_structured_output.assert_called_once_with(
        dict, include_raw=True
    )


@pytest.mark.asyncio
async def test_generate_structured_rejects_non_mapping_envelope(
    mock_ollama_llm, message_history
):
    runnable = SimpleNamespace(ainvoke=AsyncMock(return_value='invalid'))
    mock_ollama_llm.llm.with_structured_output.return_value = runnable
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    with pytest.raises(TypeError, match='invalid envelope'):
        await engine.generate(message_history, 'prompt', output_schema=dict)


@pytest.mark.asyncio
async def test_generate_structured_raises_parsing_error(
    mock_ollama_llm, message_history
):
    parsing_error = ValueError('schema mismatch')
    runnable = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value={
                'parsed': None,
                'raw': AIMessage(content='invalid json'),
                'parsing_error': parsing_error,
            }
        )
    )
    mock_ollama_llm.llm.with_structured_output.return_value = runnable
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    with pytest.raises(ValueError, match='parsing failed') as error:
        await engine.generate(message_history, 'prompt', output_schema=dict)

    assert error.value.__cause__ is parsing_error


@pytest.mark.asyncio
async def test_generate_rejects_non_message_response(
    mock_ollama_llm, message_history
):
    mock_ollama_llm.llm.ainvoke = AsyncMock(return_value='invalid')
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    with pytest.raises(TypeError, match='invalid message'):
        await engine.generate(message_history, 'prompt')


@pytest.mark.asyncio
async def test_stream_emits_text_deltas(mock_ollama_llm, message_history):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    chunks = [chunk async for chunk in engine.stream(message_history, 'prompt')]

    assert [
        chunk.text_delta
        for chunk in chunks
        if isinstance(chunk, GenerationChunk)
    ] == ['first ', 'last']


@pytest.mark.asyncio
async def test_stream_ends_with_generation_final(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]

    assert isinstance(events[-1], GenerationFinal)


@pytest.mark.asyncio
async def test_stream_final_contains_usage_metadata(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]
    final = next(
        event for event in events if isinstance(event, GenerationFinal)
    )

    assert final.usage.output_tokens == EXPECTED_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_stream_skips_non_chunk_responses(
    mock_ollama_llm, message_history
):
    async def stream_non_chunk(*args, **kwargs):
        yield AIMessage(content='not a chunk')
        yield AIMessageChunk(content='valid chunk')

    mock_ollama_llm.llm.astream = MagicMock(side_effect=stream_non_chunk)
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]

    assert events[0] == GenerationChunk(text_delta='valid chunk')
    assert isinstance(events[1], GenerationFinal)
    assert events[1].raw_text == 'valid chunk'


@pytest.mark.asyncio
async def test_stream_final_contains_aggregated_text(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]
    final = next(
        event for event in events if isinstance(event, GenerationFinal)
    )

    assert final.raw_text == 'first last'


@pytest.mark.asyncio
async def test_stream_final_reports_all_available_metadata(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    events = [event async for event in engine.stream(message_history, 'prompt')]
    final = next(
        event for event in events if isinstance(event, GenerationFinal)
    )

    assert (
        final.usage.model,
        final.usage.input_tokens,
        final.usage.output_tokens,
        final.usage.total_tokens,
        final.usage.tokens_per_second,
        final.usage.finish_reason,
    ) == (
        'test-model',
        8,
        EXPECTED_OUTPUT_TOKENS,
        28,
        EXPECTED_TOKENS_PER_SECOND,
        'stop',
    )


@pytest.mark.asyncio
async def test_stream_emits_tool_call_deltas(
    mock_ollama_tool_call_llm, message_history, sample_tool
):
    engine = OllamaEngine(llm=mock_ollama_tool_call_llm.llm)

    chunks = [
        chunk
        async for chunk in engine.stream(
            message_history, 'prompt', tools=[sample_tool]
        )
    ]

    assert chunks[0] == GenerationChunk(
        text_delta='Checking ',
        tool_call_delta=ToolCallDelta(
            index=0,
            id='call-1',
            name='lookup_weather',
            args_json_delta='{"city":',
        ),
    )


@pytest.mark.asyncio
async def test_stream_final_contains_aggregated_tool_call(
    mock_ollama_tool_call_llm, message_history, sample_tool
):
    engine = OllamaEngine(llm=mock_ollama_tool_call_llm.llm)

    events = [
        event
        async for event in engine.stream(
            message_history, 'prompt', tools=[sample_tool]
        )
    ]
    final = next(
        event for event in events if isinstance(event, GenerationFinal)
    )

    assert final.tool_calls == [
        ToolCall('call-1', 'lookup_weather', {'city': 'Paris'})
    ]


@pytest.mark.asyncio
async def test_stream_passes_messages_and_config(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    _ = [
        chunk
        async for chunk in engine.stream(
            message_history, 'system instructions', temperature=0.5
        )
    ]

    mock_ollama_llm.llm.astream.assert_called_once_with(
        [
            SystemMessage(content='system instructions'),
            HumanMessage(content='user question'),
            AIMessage(content='previous answer'),
        ],
        temperature=0.5,
    )
