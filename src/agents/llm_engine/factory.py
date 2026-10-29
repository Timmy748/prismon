from agents.llm_engine.base import ILLMEngine
from agents.llm_engine.ollama import OllamaEngine
from agents.llm_engine.openrouter import OpenRouterEngine


def create_llm_engine(api_key: str, provider: str) -> ILLMEngine:
    provider = provider.strip().casefold()
    if provider == 'ollama':
        return OllamaEngine(api_key=api_key)
    if provider == 'openrouter':
        return OpenRouterEngine(api_key=api_key)
    raise ValueError(
        f'Unsupported LLM_PROVIDER {provider!r}; '
        "expected 'ollama' or 'openrouter'"
    )
