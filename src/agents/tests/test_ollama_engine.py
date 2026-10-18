from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.llm_engine.ollama import OllamaEngine


def test_constructor_configures_chat_ollama(monkeypatch, ollama_settings):
    chat_ollama = MagicMock()
    get_settings = MagicMock(return_value=ollama_settings)
    chat_ollama_factory = MagicMock(return_value=chat_ollama)
    monkeypatch.setattr('agents.llm_engine.ollama.get_settings', get_settings)
    monkeypatch.setattr(
        'agents.llm_engine.ollama.ChatOllama', chat_ollama_factory
    )

    engine = OllamaEngine()

    chat_ollama_factory.assert_called_once_with(
        base_url='http://ollama:11434', model='test-model', temperature=0.25
    )
    assert engine._llm is chat_ollama


def test_bind_tools_returns_new_engine_with_bound_llm(
    mock_ollama_llm, sample_tool
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    bound_engine = engine.bind_tools([sample_tool])

    mock_ollama_llm.llm.bind_tools.assert_called_once()
    assert (
        mock_ollama_llm.llm.bind_tools.call_args.args[0][0]['function']['name']
        == 'lookup_weather'
    )
    assert bound_engine is not engine
    assert bound_engine._llm is mock_ollama_llm.bound_llm


@pytest.mark.asyncio
async def test_agenerate_uses_message_content_and_returns_model_content(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    response = await engine.generate(
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
    assert response == 'model answer'


@pytest.mark.asyncio
async def test_astream_yields_nonempty_chunk_content(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    chunks = [
        chunk
        async for chunk in engine.stream(
            message_history, 'system instructions', temperature=0.5
        )
    ]

    assert chunks == ['first ', 'last']
    mock_ollama_llm.llm.astream.assert_called_once_with(
        [
            SystemMessage(content='system instructions'),
            HumanMessage(content='user question'),
            AIMessage(content='previous answer'),
        ],
        temperature=0.5,
    )


@pytest.mark.asyncio
async def test_agenerate_structured_returns_schema_result(
    mock_ollama_llm, message_history
):
    engine = OllamaEngine(llm=mock_ollama_llm.llm)

    response = await engine.generate_strutured(
        dict, message_history, 'system instructions', include_raw=False
    )

    mock_ollama_llm.llm.with_structured_output.assert_called_once_with(dict)
    mock_ollama_llm.structured_llm.ainvoke.assert_awaited_once_with(
        [
            SystemMessage(content='system instructions'),
            HumanMessage(content='user question'),
            AIMessage(content='previous answer'),
        ],
        include_raw=False,
    )
    assert response == {'result': 'structured'}
