from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agents.llm_engine.factory import create_llm_engine


def test_create_llm_engine_uses_ollama_for_default_provider(monkeypatch):
    engine = object()
    ollama_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(
        'agents.llm_engine.factory.get_settings',
        lambda: SimpleNamespace(LLM_PROVIDER=' ollama '),
    )
    monkeypatch.setattr('agents.llm_engine.factory.OllamaEngine', ollama_engine)

    result = create_llm_engine()

    assert result is engine
    ollama_engine.assert_called_once_with()


def test_create_llm_engine_selects_openrouter(monkeypatch):
    engine = object()
    openrouter_engine = MagicMock(return_value=engine)
    monkeypatch.setattr(
        'agents.llm_engine.factory.get_settings',
        lambda: SimpleNamespace(LLM_PROVIDER=' OpenRouter '),
    )
    monkeypatch.setattr(
        'agents.llm_engine.factory.OpenRouterEngine', openrouter_engine
    )

    result = create_llm_engine()

    assert result is engine
    openrouter_engine.assert_called_once_with()


def test_create_llm_engine_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(
        'agents.llm_engine.factory.get_settings',
        lambda: SimpleNamespace(LLM_PROVIDER='unknown'),
    )

    with pytest.raises(ValueError, match='Unsupported LLM_PROVIDER'):
        create_llm_engine()
