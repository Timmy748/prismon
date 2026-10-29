from unittest.mock import MagicMock

import pytest

from agents.llm_engine.factory import create_llm_engine


def test_create_llm_engine_passes_api_key_to_ollama(monkeypatch):
    engine = object()
    ollama_engine = MagicMock(return_value=engine)
    monkeypatch.setattr('agents.llm_engine.factory.OllamaEngine', ollama_engine)

    result = create_llm_engine(api_key='api-secret', provider=' ollama ')

    assert result is engine
    ollama_engine.assert_called_once_with(api_key='api-secret')


def test_create_llm_engine_selects_openrouter(monkeypatch):
    engine = object()
    openrouter_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(
        'agents.llm_engine.factory.OpenRouterEngine', openrouter_engine
    )

    result = create_llm_engine(api_key='api-secret', provider=' OpenRouter ')

    assert result is engine
    openrouter_engine.assert_called_once_with(api_key='api-secret')


def test_create_llm_engine_rejects_unsupported_provider(monkeypatch):
    with pytest.raises(ValueError, match='Unsupported LLM_PROVIDER'):
        create_llm_engine(api_key='api-secret', provider='unknown')
