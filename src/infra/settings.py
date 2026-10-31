from dataclasses import field
from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        case_sensitive=False, extra='ignore', env_file='.env'
    )

    DATABASE_URL: str = field(init=False)

    # Logging and telemetry
    OTEL_SERVICE_NAME: str = field(init=False)
    OTEL_EXPORTER_OTLP_ENDPOINT: str = field(init=False)
    OTEL_EXPORTER_OTLP_LOGS_ENDPOINT: str = field(init=False)

    # Project storage and API key encryption
    RUSTFS_ENDPOINT_URL: str = field(init=False)
    RUSTFS_PUBLIC_ENDPOINT_URL: str = field(init=False)
    RUSTFS_BUCKET: str = field(init=False)
    RUSTFS_ACCESS_KEY: str = field(init=False)
    RUSTFS_SECRET_KEY: str = field(init=False)
    RUSTFS_REGION: str = field(init=False)
    RUSTFS_PRESIGNED_URL_TTL_SECONDS: int = Field(default=3600, ge=1, le=604800)
    API_KEY_KEK: SecretStr = SecretStr('')

    # Identity
    PASSWORD_PEPPER: SecretStr = field(init=False)
    JWT_SECRET_KEY: SecretStr = field(init=False)
    JWT_ALGORITHM: str = 'HS256'
    JWT_EXPIRES_IN_MINUTES: int = 15

    # Agents and LLM providers
    OLLAMA_BASE_URL: str = 'http://ollama:11434'
    OLLAMA_MODEL: str = 'bonsai-2:4b'
    OLLAMA_TEMPERATURE: float = 0.0
    LLM_PROVIDER: str = 'ollama'
    OPENROUTER_MODEL: str = ''
    OPENROUTER_TEMPERATURE: float = 0.0


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    return Settings()
