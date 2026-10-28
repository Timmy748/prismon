from agents.llm_engine.base import ILLMEngine
from agents.llm_engine.ollama import OllamaEngine
from agents.llm_engine.openrouter import OpenRouterEngine
from agents.settings import get_settings


def create_llm_engine() -> ILLMEngine:
    provider = get_settings().LLM_PROVIDER.strip().casefold()
    if provider == 'ollama':
        return OllamaEngine()
    if provider == 'openrouter':
        return OpenRouterEngine()
    raise ValueError(
        f'Unsupported LLM_PROVIDER {provider!r}; '
        "expected 'ollama' or 'openrouter'"
    )
