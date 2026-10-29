from dataclasses import field
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):  # pragma: no cover
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )
    DATABASE_URL: str = field(init=False)
    OLLAMA_BASE_URL: str = 'http://ollama:11434'
    OLLAMA_MODEL: str = 'bonsai-2:4b'
    OLLAMA_TEMPERATURE: float = 0.0
    LLM_PROVIDER: str = 'ollama'
    OPENROUTER_MODEL: str = ''
    OPENROUTER_TEMPERATURE: float = 0.0


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
